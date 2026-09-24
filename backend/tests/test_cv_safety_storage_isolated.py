"""CV safety + storage failure regressions (isolated local Mongo, no real external calls)."""

import os
import sys
import uuid
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
import requests
from docx import Document
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

import cv_recheck_service
import resume_read_safety
import server
from background_processor import ProcessingJob
from models import User, UserRole
from storage_service import ResumeStorageError


pytestmark = pytest.mark.anyio


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _user(role: UserRole = UserRole.ADMIN, user_id: str = "admin-cv"):
    return User(id=user_id, email=f"{user_id}@example.com", name=user_id, role=role)


@pytest.fixture
async def isolated_db():
    """Temporary LOCAL Mongo with server-level db overrides for all touched services."""
    mongo_url = os.environ.get("MONGO_URL")
    assert mongo_url, "MONGO_URL no configurada"
    assert urlparse(mongo_url).hostname in {"localhost", "127.0.0.1", "::1"}, "Solo Mongo local permitido"

    db_name = f"test_cv_safety_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[db_name]

    original_db = server.db
    server.db = test_db

    touched_services = []
    for name in (
        "background_processor",
        "cv_version_service",
        "assignment_service",
        "duplicate_detector",
        "duplicate_detector_v2",
        "candidate_merger",
        "job_matching_service",
        "user_service",
        "export_service",
        "smart_folder_service",
        "hybrid_search_service",
    ):
        service = getattr(server, name, None)
        if service is not None and hasattr(service, "db"):
            touched_services.append((service, service.db))
            service.db = test_db

    await test_db.industries.insert_many([
        {"key": "technology", "name_es": "Tecnología"},
        {"key": "finance", "name_es": "Finanzas"},
    ])
    await test_db.functional_areas.insert_many([
        {"key": "it", "name_es": "TI"},
        {"key": "operations", "name_es": "Operaciones"},
    ])

    try:
        yield test_db
    finally:
        server.db = original_db
        for service, original in touched_services:
            service.db = original
        server.app.dependency_overrides.clear()
        await client.drop_database(db_name)
        client.close()


@pytest.fixture
async def api_client(isolated_db):
    current = {"user": _user()}

    def _override_user():
        return current["user"]

    server.app.dependency_overrides[server.get_current_user] = _override_user
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, current


async def _insert_candidate(db, candidate_id: str, **extra):
    now = _iso_now()
    doc = {
        "id": candidate_id,
        "full_name": f"TEST {candidate_id}",
        "notes": [{"id": "n1", "note": "keep", "created_by": "u", "created_at": now}],
        "tags": ["keep-tag"],
        "job_assignments": [{"job_id": "j1", "stage": "new", "assigned_by": "u", "assigned_at": now, "updated_at": now}],
        "resume_files": [],
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    doc.update(extra)
    await db.candidates.insert_one(doc)


# Module: /api/atlas/classify/{id} unreadable/missing resume safety
async def test_classify_missing_resume_returns_422_no_llm_and_sets_manual_capture(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-classify-422")
    previous_ai = {
        "industry": "technology",
        "functional_area": "it",
        "seniority": "senior",
        "confidence_score": 0.88,
        "approved_by_recruiter": False,
        "classified_at": _iso_now(),
    }
    await _insert_candidate(isolated_db, "cand-no-resume", ai_classification=previous_ai)

    calls = {"llm": 0}

    async def _must_not_call(*_args, **_kwargs):
        calls["llm"] += 1
        raise AssertionError("classify_candidate should not be called when resume is missing")

    monkeypatch.setattr(server.atlas_service, "classify_candidate", _must_not_call)
    response = await client.post("/api/atlas/classify/cand-no-resume")

    assert response.status_code == 422
    assert calls["llm"] == 0
    payload = response.json()
    assert "Requiere captura manual" in payload["detail"]

    saved = await isolated_db.candidates.find_one({"id": "cand-no-resume"}, {"_id": 0})
    assert saved["review_status"] == "manual_capture"
    assert saved["ai_classification"] is None
    assert saved["classification_read_error"]["reason"] == "missing_resume"
    assert saved["classification_read_error"]["previous_classification"]["industry"] == "technology"
    assert saved["notes"][0]["note"] == "keep"
    assert saved["tags"] == ["keep-tag"]
    assert saved["job_assignments"][0]["job_id"] == "j1"

    pending_ids = await client.get("/api/atlas/classifications/pending/ids")
    pending_count = await client.get("/api/atlas/classifications/pending/count")
    assert pending_ids.status_code == 200
    assert pending_count.status_code == 200
    assert "cand-no-resume" in pending_ids.json()["candidate_ids"]
    assert pending_count.json()["count"] >= 1


# Module: /api/atlas/classify/{id} success path and error marker clear
async def test_classify_success_clears_read_error_and_persists_ai_once(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-classify-ok")
    reference = {
        "key": "atlas-talent-vault/resumes/cand-ok/new.docx",
        "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    await _insert_candidate(
        isolated_db,
        "cand-ok",
        resume_files=[{
            "file_name": "new.docx",
            "file_path": reference["key"],
            "file_type": reference["type"],
            "upload_date": _iso_now(),
        }],
        classification_read_error={"reason": "unreadable_resume", "message": "old"},
    )

    calls = {"llm": 0}

    async def _fake_readable_resume(_db, _candidate):
        return ("Texto legible y suficiente para clasificación con detalle funcional y sectorial.", reference)

    async def _fake_current_resume(_db, _candidate):
        return reference

    async def _fake_classify(_candidate, resume_text):
        calls["llm"] += 1
        assert len(resume_text.strip()) > 50
        return {
            "industry": "technology",
            "functional_area": "it",
            "seniority": "senior",
            "confidence_score": 0.91,
            "suggested_tags": ["infra"],
        }

    monkeypatch.setattr(server, "readable_resume", _fake_readable_resume)
    monkeypatch.setattr(cv_recheck_service, "current_resume", _fake_current_resume)
    monkeypatch.setattr(server.atlas_service, "classify_candidate", _fake_classify)

    response = await client.post("/api/atlas/classify/cand-ok")
    assert response.status_code == 200
    assert calls["llm"] == 1
    assert response.json()["industry"] == "technology"

    saved = await isolated_db.candidates.find_one({"id": "cand-ok"}, {"_id": 0})
    assert saved["ai_classification"]["industry"] == "technology"
    assert saved["review_status"] == "classified"
    assert saved.get("classification_read_error") in (None, {})


# Module: /api/atlas/classify/{id} conflict + not found
async def test_classify_conflict_and_deleted_not_found(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-classify-conflict")

    reference = {"key": "atlas-talent-vault/resumes/cand-conflict/cv.pdf", "type": "application/pdf"}
    await _insert_candidate(
        isolated_db,
        "cand-conflict",
        resume_files=[{"file_name": "cv.pdf", "file_path": reference["key"], "file_type": "application/pdf", "upload_date": _iso_now()}],
    )

    async def _fake_readable_resume(_db, _candidate):
        return ("Texto suficiente para intentar clasificar con IA y detectar conflicto.", reference)

    async def _changed_resume(_db, _candidate):
        return {"key": "atlas-talent-vault/resumes/cand-conflict/other.pdf", "type": "application/pdf"}

    async def _fake_classify(_candidate, _text):
        return {"industry": "technology", "functional_area": "it", "seniority": "senior", "confidence_score": 0.9, "suggested_tags": []}

    monkeypatch.setattr(server, "readable_resume", _fake_readable_resume)
    monkeypatch.setattr(cv_recheck_service, "current_resume", _changed_resume)
    monkeypatch.setattr(server.atlas_service, "classify_candidate", _fake_classify)

    conflict = await client.post("/api/atlas/classify/cand-conflict")
    assert conflict.status_code == 409

    missing = await client.post("/api/atlas/classify/not-exists")
    assert missing.status_code == 404


# Module: /api/candidates/upload-resume failure behavior for new/existing candidate
async def test_upload_resume_storage_failure_new_and_existing_keep_integrity(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-upload-fail")

    async def _fake_parse(_text):
        return {"full_name": "TEST New", "email": None, "phone": None, "skills": [], "languages": []}

    async def _fake_classify(*_args, **_kwargs):
        return {
            "industry": "technology",
            "functional_area": "it",
            "seniority": "senior",
            "confidence_score": 0.9,
            "suggested_tags": [],
            "review_status": "classified",
            "review_message": "",
        }

    async def _fake_summary(*_args, **_kwargs):
        return "summary"

    async def _fake_embedding(*_args, **_kwargs):
        return []

    async def _fake_hard_duplicates(*_args, **_kwargs):
        return None

    async def _fake_soft_duplicates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(server.DocumentParser, "extract_text_from_bytes", lambda *_: "Texto legible " * 10)
    monkeypatch.setattr(server.atlas_service, "parse_resume", _fake_parse)
    monkeypatch.setattr(server, "classify_with_refinement", _fake_classify)
    monkeypatch.setattr(server.atlas_service, "generate_summary", _fake_summary)
    monkeypatch.setattr(server.embedding_service, "generate_candidate_embedding", _fake_embedding)
    monkeypatch.setattr(server.duplicate_detector_v2, "detect_hard_duplicates", _fake_hard_duplicates)
    monkeypatch.setattr(server.duplicate_detector_v2, "detect_soft_duplicates", _fake_soft_duplicates)
    monkeypatch.setattr(server.storage_service, "upload_resume", lambda *_: (_ for _ in ()).throw(ResumeStorageError(3)))

    files = {"file": ("new.pdf", b"%PDF-1.4 synthetic", "application/pdf")}
    new_resp = await client.post("/api/candidates/upload-resume", files=files)
    assert new_resp.status_code == 200
    new_payload = new_resp.json()
    assert new_payload["status"] == "failed"
    assert new_payload.get("cv_storage_issue", {}).get("status") == "failed"

    new_candidate = await isolated_db.candidates.find_one({"id": new_payload["candidate_id"]}, {"_id": 0})
    assert new_candidate["resume_files"] == []
    assert new_candidate["cv_storage_issue"]["status"] == "failed"
    assert await isolated_db.cv_versions.count_documents({"candidate_id": new_payload["candidate_id"]}) == 0

    existing_id = "cand-existing-upload"
    prev_resume = [{"file_name": "old.pdf", "file_path": "atlas-talent-vault/resumes/existing/old.pdf", "file_type": "application/pdf", "upload_date": _iso_now()}]
    await _insert_candidate(isolated_db, existing_id, resume_files=prev_resume, industry="finance", functional_area="operations")

    existing_resp = await client.post(
        "/api/candidates/upload-resume",
        files={"file": ("replace.pdf", b"%PDF-1.4 replace", "application/pdf")},
        data={"candidate_id": existing_id},
    )
    assert existing_resp.status_code == 200
    existing_payload = existing_resp.json()
    assert existing_payload["status"] == "failed"

    existing_doc = await isolated_db.candidates.find_one({"id": existing_id}, {"_id": 0})
    assert len(existing_doc["resume_files"]) == 1
    assert existing_doc["resume_files"][0]["file_name"] == "old.pdf"
    assert existing_doc["industry"] == "finance"
    assert existing_doc["cv_storage_issue"]["status"] == "failed"


# Module: /api/candidates/upload-resume successful attachment clears previous marker
async def test_upload_resume_existing_success_clears_storage_issue(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-upload-ok")

    existing_id = "cand-existing-ok"
    await _insert_candidate(
        isolated_db,
        existing_id,
        resume_files=[{"file_name": "old.pdf", "file_path": "atlas-talent-vault/resumes/existing/old.pdf", "file_type": "application/pdf", "upload_date": _iso_now()}],
        cv_storage_issue={"status": "failed", "message": "prev"},
    )

    monkeypatch.setattr(server.storage_service, "upload_resume", lambda *_: {
        "storage_path": f"atlas-talent-vault/resumes/{existing_id}/new.pdf",
        "content_type": "application/pdf",
        "size": 100,
        "file_uuid": "u1",
    })

    ok = await client.post(
        "/api/candidates/upload-resume",
        files={"file": ("new.pdf", b"%PDF-1.4 ok", "application/pdf")},
        data={"candidate_id": existing_id},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] in {"success", "partial_success"}

    saved = await isolated_db.candidates.find_one({"id": existing_id}, {"_id": 0})
    assert len(saved["resume_files"]) == 2
    assert saved.get("cv_storage_issue") in (None, {})


# Module: /api/candidates/{id}/update-cv failure must mark durable issue and keep profile/CV untouched
async def test_update_cv_storage_failure_marks_issue_without_adding_version(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-update-cv")

    candidate_id = "cand-update-cv"
    original_resume = [{"file_name": "old.pdf", "file_path": "atlas-talent-vault/resumes/update/old.pdf", "file_type": "application/pdf", "upload_date": _iso_now()}]
    await _insert_candidate(isolated_db, candidate_id, resume_files=original_resume, current_title="Old Title")

    async def _fake_current_user(_credentials=None):
        return _user(UserRole.ADMIN, "admin-update-cv")

    monkeypatch.setattr(server, "get_current_user", _fake_current_user)
    monkeypatch.setattr(server.storage_service, "upload_resume", lambda *_: (_ for _ in ()).throw(ResumeStorageError(3)))

    resp = await client.post(
        f"/api/candidates/{candidate_id}/update-cv",
        files={"file": ("new.docx", b"PK\x03\x04synthetic", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 503

    doc = await isolated_db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    assert len(doc["resume_files"]) == 1
    assert doc["resume_files"][0]["file_name"] == "old.pdf"
    assert doc["current_title"] == "Old Title"
    assert doc["cv_storage_issue"]["status"] == "failed"
    assert await isolated_db.cv_versions.count_documents({"candidate_id": candidate_id}) == 0


# Module: process_cv_job storage fail keeps failed status and candidate marker
async def test_process_cv_job_storage_failure_ends_failed_and_sets_marker(isolated_db, monkeypatch):
    async def _fake_parse_resume(*_args, **_kwargs):
        return {"full_name": "Batch User", "skills": [], "languages": []}

    async def _fake_classify(*_args, **_kwargs):
        return {
            "industry": "technology",
            "functional_area": "it",
            "seniority": "senior",
            "confidence_score": 0.9,
            "suggested_tags": [],
            "review_status": "classified",
            "review_message": "",
        }

    async def _fake_summary(*_args, **_kwargs):
        return "summary"

    async def _fake_duplicates(*_args, **_kwargs):
        return []

    async def _fake_embedding(*_args, **_kwargs):
        return []

    monkeypatch.setattr(server.DocumentParser, "extract_with_details", lambda *_: {"text": "Texto legible " * 10, "text_chars": 200, "readable": True, "warnings": [], "pages": []})
    monkeypatch.setattr(server.atlas_service, "parse_resume", _fake_parse_resume)
    monkeypatch.setattr(server, "classify_with_refinement", _fake_classify)
    monkeypatch.setattr(server.atlas_service, "generate_summary", _fake_summary)
    monkeypatch.setattr(server.duplicate_detector, "detect_duplicates", _fake_duplicates)
    monkeypatch.setattr(server.storage_service, "upload_resume", lambda *_: (_ for _ in ()).throw(ResumeStorageError(3)))
    monkeypatch.setattr(server.embedding_service, "generate_candidate_embedding", _fake_embedding)

    job = ProcessingJob(job_id="job-storage-fail", batch_id="batch-1", file_name="failing.pdf", file_size=10)
    result = await server.process_cv_job(job, b"%PDF-1.4", {"user_id": "u-admin", "file_name": "failing.pdf", "content_type": "application/pdf"})

    assert result["status"] == "failed"
    assert any(err["type"] == "storage_upload_failed" for err in result.get("errors", []))

    saved = await isolated_db.candidates.find_one({"id": result["candidate_id"]}, {"_id": 0, "resume_files": 1, "cv_storage_issue": 1})
    assert saved["resume_files"] == []
    assert saved["cv_storage_issue"]["status"] == "failed"


def _docx_bytes(text):
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


CV_TEXT = 'Responsable de operaciones y tecnología con experiencia en liderazgo de equipos, gestión de proyectos y mejora continua. Implementación de sistemas, análisis de procesos y resultados verificables durante diez años.'


@pytest.mark.parametrize('mode,reason', [
    ('missing_local', 'local_read_failed'), ('remote_404', 'remote_read_failed'),
    ('remote_timeout', 'remote_read_failed'), ('corrupt', 'extraction_failed'),
    ('blank', 'unreadable_resume'), ('invalid_path', 'invalid_reference'),
])
async def test_real_reader_failure_never_calls_llm(api_client, isolated_db, monkeypatch, tmp_path, mode, reason):
    client, _ = api_client
    monkeypatch.setattr(resume_read_safety, 'ROOT', tmp_path)
    key = 'atlas-talent-vault/resumes/test/original.docx'
    if mode == 'missing_local':
        key = 'uploads/resumes/fixture/missing.docx'
    elif mode == 'invalid_path':
        key = '../../not-a-cv.docx'
    await _insert_candidate(isolated_db, 'reader-failure', resume_files=[{
        'file_name': 'original.docx', 'file_path': key, 'file_type': '.docx', 'upload_date': _iso_now(),
    }])

    def fake_download(_key):
        if mode == 'remote_404':
            response = requests.Response(); response.status_code = 404
            raise requests.HTTPError('synthetic-not-found', response=response)
        if mode == 'remote_timeout':
            raise requests.Timeout('synthetic timeout')
        return (_docx_bytes('') if mode == 'blank' else b'not-a-docx'), 'application/octet-stream'

    async def no_llm(*_args, **_kwargs):
        pytest.fail('Unreadable CV reached LLM')

    monkeypatch.setattr(server.storage_service, 'get_object', fake_download)
    monkeypatch.setattr(server.atlas_service, 'classify_candidate', no_llm)
    response = await client.post('/api/atlas/classify/reader-failure')
    assert response.status_code == 422
    saved = await isolated_db.candidates.find_one({'id': 'reader-failure'}, {'_id': 0})
    assert saved['classification_read_error']['reason'] == reason
    assert saved['review_status'] == 'manual_capture'
    assert saved['ai_classification'] is None
    assert 'reader-failure' in (await client.get('/api/atlas/classifications/pending/ids')).json()['candidate_ids']


@pytest.mark.parametrize('mode', ['remote_current_version', 'remote_newest_resume', 'local_readable'])
async def test_actual_docx_extraction_selects_current_cv(api_client, isolated_db, monkeypatch, tmp_path, mode):
    client, _ = api_client
    monkeypatch.setattr(resume_read_safety, 'ROOT', tmp_path)
    old = {'file_name': 'old.docx', 'file_path': 'atlas-talent-vault/resumes/docx/old.docx', 'file_type': '.docx', 'upload_date': '2020-01-01T00:00:00Z'}
    key = 'atlas-talent-vault/resumes/docx/current.docx'
    raw = _docx_bytes(CV_TEXT)
    if mode == 'local_readable':
        key = 'uploads/resumes/docx/current.docx'
        path = tmp_path / key
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
    recent = {'file_name': 'current.docx', 'file_path': key, 'file_type': '.docx', 'upload_date': _iso_now()}
    await _insert_candidate(isolated_db, 'docx-real', resume_files=[old] if mode == 'remote_current_version' else [old, recent])
    if mode == 'remote_current_version':
        await isolated_db.cv_versions.insert_one({'id': 'current-version', 'candidate_id': 'docx-real', 'file_key': key, 'file_name': 'current.docx', 'file_type': '.docx', 'is_active': True, 'is_current': True})
    downloads, texts = [], []

    def fake_download(requested):
        downloads.append(requested)
        assert requested == key
        return raw, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

    async def fake_classify(_candidate, text):
        texts.append(text)
        assert CV_TEXT in text
        return {'industry': 'technology', 'functional_area': 'it', 'seniority': 'senior', 'confidence_score': 0.9}

    monkeypatch.setattr(server.storage_service, 'get_object', fake_download)
    monkeypatch.setattr(server.atlas_service, 'classify_candidate', fake_classify)
    response = await client.post('/api/atlas/classify/docx-real')
    assert response.status_code == 200, response.text
    assert len(texts) == 1
    assert len(downloads) == (0 if mode == 'local_readable' else 1)


async def test_update_cv_recovery_clears_error_and_preserves_old_cv(api_client, isolated_db, monkeypatch):
    client, _ = api_client
    await _insert_candidate(isolated_db, 'recovery', cv_storage_issue={'status': 'failed', 'message': 'previous failure'},
                            resume_files=[{'file_name': 'old.docx', 'file_path': 'atlas-talent-vault/resumes/recovery/old.docx', 'file_type': '.docx', 'upload_date': _iso_now()}])

    async def fake_user(_credentials=None):
        return _user()

    async def fake_parse(_text):
        return {'full_name': 'Synthetic Recovery'}

    monkeypatch.setattr(server, 'get_current_user', fake_user)
    monkeypatch.setattr(server.atlas_service, 'parse_resume', fake_parse)
    monkeypatch.setattr(server.storage_service, 'upload_resume', lambda *_: {
        'storage_path': 'atlas-talent-vault/resumes/recovery/new.docx',
        'content_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    response = await client.post('/api/candidates/recovery/update-cv',
        files={'file': ('new.docx', _docx_bytes(CV_TEXT), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},
        headers={'Authorization': 'Bearer fixture-only-token'})
    assert response.status_code == 200, response.text
    saved = await isolated_db.candidates.find_one({'id': 'recovery'}, {'_id': 0})
    assert not saved.get('cv_storage_issue')
    assert [resume['file_name'] for resume in saved['resume_files']] == ['old.docx', 'new.docx']
    assert await isolated_db.cv_versions.count_documents({'candidate_id': 'recovery', 'is_current': True}) == 1


async def test_cv_removed_during_classification_returns_conflict_not_success(api_client, isolated_db, monkeypatch):
    client, _ = api_client
    await _insert_candidate(isolated_db, 'removed-mid-classify', resume_files=[{
        'file_name': 'original.docx', 'file_path': 'atlas-talent-vault/resumes/removed/original.docx',
        'file_type': '.docx', 'upload_date': _iso_now(),
    }])
    monkeypatch.setattr(server.storage_service, 'get_object', lambda _key: (_docx_bytes(CV_TEXT), 'application/octet-stream'))

    async def fake_classify(_candidate, _text):
        await isolated_db.candidates.update_one({'id': 'removed-mid-classify'}, {'$set': {'resume_files': [], 'updated_at': _iso_now()}})
        return {'industry': 'technology', 'functional_area': 'it', 'seniority': 'senior', 'confidence_score': 0.9}

    monkeypatch.setattr(server.atlas_service, 'classify_candidate', fake_classify)
    response = await client.post('/api/atlas/classify/removed-mid-classify')
    assert response.status_code == 409, response.text
    candidate = await isolated_db.candidates.find_one({'id': 'removed-mid-classify'}, {'_id': 0})
    assert candidate['resume_files'] == []
    assert not candidate.get('ai_classification')
