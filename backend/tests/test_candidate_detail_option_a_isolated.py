"""Option A isolated regression: classify button backend effects, manual field persistence, and permissions."""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

import server  # noqa: E402
from models import User, UserRole  # noqa: E402


pytestmark = pytest.mark.anyio


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _user(role: UserRole, user_id: str):
    return User(id=user_id, email=f"{user_id}@example.com", name=user_id, role=role)


@pytest.fixture
async def isolated_db():
    """Temporary LOCAL MongoDB with full db overrides to avoid shared Atlas writes."""
    mongo_url = os.environ.get("MONGO_URL")
    assert mongo_url, "MONGO_URL no configurada"
    assert urlparse(mongo_url).hostname in {"localhost", "127.0.0.1", "::1"}, "Prueba permitida exclusivamente en Mongo local"

    db_name = f"test_option_a_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[db_name]

    original_db = server.db
    original_bp_db = server.background_processor.db
    original_assignment_db = server.assignment_service.db
    server.db = test_db
    server.background_processor.db = test_db
    server.assignment_service.db = test_db

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
        server.background_processor.db = original_bp_db
        server.assignment_service.db = original_assignment_db
        server.app.dependency_overrides.clear()
        await client.drop_database(db_name)
        client.close()


@pytest.fixture
async def api_client(isolated_db):
    """ASGI client with switchable authenticated user (no startup lifecycle)."""
    current = {"user": _user(UserRole.ADMIN, "admin-option-a")}

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
        "industry": None,
        "functional_area": None,
        "seniority": None,
        "years_experience": None,
        "ai_classification": {"approved_by_recruiter": False, "confidence_score": 0.2, "classified_at": now},
        "notes": [],
        "resume_files": [],
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    doc.update(extra)
    await db.candidates.insert_one(doc)


# Module: /api/atlas/classify/{id} + isolated persistence
async def test_classify_stores_ai_classification_and_updates_candidate(api_client, isolated_db, monkeypatch):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-classify")
    await _insert_candidate(
        isolated_db,
        "cand-classify",
        resume_files=[{
            "file_name": "cv.docx",
            "file_path": "atlas-talent-vault/resumes/cand-classify/cv.docx",
            "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "upload_date": _iso_now(),
        }],
    )

    calls = {"count": 0}

    async def _fake_classify(candidate_data, resume_text):
        calls["count"] += 1
        assert candidate_data["id"] == "cand-classify"
        assert isinstance(resume_text, str) and len(resume_text.strip()) >= 50
        return {
            "industry": "technology",
            "functional_area": "it",
            "seniority": "senior",
            "confidence_score": 0.91,
            "suggested_tags": ["liderazgo"],
        }

    async def _fake_readable_resume(_db, _candidate):
        return (
            "Experiencia sólida en operaciones, liderazgo, estrategia y resultados durante más de diez años.",
            {
                "key": "atlas-talent-vault/resumes/cand-classify/cv.docx",
                "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
        )

    async def _fake_current_resume(_db, _candidate):
        return {
            "key": "atlas-talent-vault/resumes/cand-classify/cv.docx",
            "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

    import cv_recheck_service
    monkeypatch.setattr(server, "readable_resume", _fake_readable_resume)
    monkeypatch.setattr(cv_recheck_service, "current_resume", _fake_current_resume)
    monkeypatch.setattr(server.atlas_service, "classify_candidate", _fake_classify)
    response = await client.post("/api/atlas/classify/cand-classify")

    assert response.status_code == 200
    body = response.json()
    assert body["industry"] == "technology"
    assert body["functional_area"] == "it"
    assert body["seniority"] == "senior"
    assert calls["count"] == 1

    doc = await isolated_db.candidates.find_one({"id": "cand-classify"}, {"_id": 0})
    assert doc["industry"] is None
    assert doc["functional_area"] is None
    assert doc["ai_classification"]["industry"] == "technology"
    assert doc["ai_classification"]["functional_area"] == "it"
    assert doc["ai_classification"]["seniority"] == "senior"


# Module: /api/atlas/classifications/manual/{id} immediate field-only save + refetch
async def test_manual_patch_each_field_persists_and_keeps_zero_vs_null(api_client, isolated_db):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-manual")
    await _insert_candidate(isolated_db, "cand-manual")

    patch_industry = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"industry": "finance"})
    patch_area = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"functional_area": "operations"})
    patch_seniority = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"seniority": "manager"})
    patch_years_zero = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"years_experience": 0})
    patch_years_null = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"years_experience": None})

    assert patch_industry.status_code == 200
    assert patch_area.status_code == 200
    assert patch_seniority.status_code == 200
    assert patch_years_zero.status_code == 200
    assert patch_years_zero.json()["years_experience"] == 0
    assert patch_years_null.status_code == 200
    assert patch_years_null.json()["years_experience"] is None

    get_candidate = await client.get("/api/candidates/cand-manual")
    assert get_candidate.status_code == 200
    candidate = get_candidate.json()
    assert candidate["industry"] == "finance"
    assert candidate["functional_area"] == "operations"
    assert candidate["seniority"] == "manager"
    assert candidate["years_experience"] is None
    assert candidate["ai_classification"]["confidence_score"] == 0.2
    assert candidate["ai_classification"]["approved_by_recruiter"] is False


# Module: permissions for manual edit + /can-edit policy
async def test_manual_permissions_admin_assigned_recruiter_allowed_others_blocked(api_client, isolated_db):
    client, current = api_client
    now = _iso_now()
    await _insert_candidate(isolated_db, "cand-permissions")
    await isolated_db.assignments.insert_one({
        "id": "assn-1",
        "candidate_id": "cand-permissions",
        "candidate_name": "TEST cand-permissions",
        "recruiter_id": "rec-assigned",
        "recruiter_name": "Rec Assigned",
        "assigned_by": "admin-1",
        "assigned_by_name": "Admin",
        "assigned_at": now,
        "status": "active",
    })

    current["user"] = _user(UserRole.ADMIN, "admin-allow")
    assert (await client.patch("/api/atlas/classifications/manual/cand-permissions", json={"industry": "technology"})).status_code == 200

    current["user"] = _user(UserRole.SUPER_ADMIN, "super-allow")
    assert (await client.patch("/api/atlas/classifications/manual/cand-permissions", json={"functional_area": "it"})).status_code == 200

    current["user"] = _user(UserRole.RECRUITER, "rec-assigned")
    assert (await client.patch("/api/atlas/classifications/manual/cand-permissions", json={"seniority": "senior"})).status_code == 200

    current["user"] = _user(UserRole.RECRUITER, "rec-unassigned")
    assert (await client.patch("/api/atlas/classifications/manual/cand-permissions", json={"industry": "finance"})).status_code == 403

    # Researcher denied even if assigned
    await isolated_db.assignments.insert_one({
        "id": "assn-2",
        "candidate_id": "cand-permissions",
        "candidate_name": "TEST cand-permissions",
        "recruiter_id": "res-assigned",
        "recruiter_name": "Res Assigned",
        "assigned_by": "admin-1",
        "assigned_by_name": "Admin",
        "assigned_at": now,
        "status": "active",
    })
    current["user"] = _user(UserRole.RESEARCHER, "res-assigned")
    assert (await client.patch("/api/atlas/classifications/manual/cand-permissions", json={"industry": "finance"})).status_code == 403

    current["user"] = _user(UserRole.RECRUITER, "rec-assigned")
    can_edit_assigned = await client.get("/api/candidates/cand-permissions/can-edit")
    assert can_edit_assigned.status_code == 200
    assert can_edit_assigned.json()["can_edit"] is True

    current["user"] = _user(UserRole.RESEARCHER, "res-assigned")
    can_edit_researcher = await client.get("/api/candidates/cand-permissions/can-edit")
    assert can_edit_researcher.status_code == 200
    assert can_edit_researcher.json()["can_edit"] is False


# Module: approved policy lock (existing 409 backend policy)
async def test_manual_patch_returns_409_when_already_approved(api_client, isolated_db):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-approved")
    await _insert_candidate(
        isolated_db,
        "cand-approved-lock",
        ai_classification={
            "industry": "technology",
            "functional_area": "it",
            "seniority": "senior",
            "confidence_score": 0.87,
            "approved_by_recruiter": True,
            "classified_at": _iso_now(),
        },
    )
    response = await client.patch("/api/atlas/classifications/manual/cand-approved-lock", json={"industry": "finance"})
    assert response.status_code == 409


# Module: optional live synthetic classify check (single call, no real CV payload)
@pytest.mark.integration_live
@pytest.mark.skipif(os.environ.get("RUN_LIVE_CLASSIFICATION_TEST") != "1", reason="La llamada IA real requiere autorización explícita")
async def test_live_classify_single_synthetic_candidate_if_key_available(api_client, isolated_db):
    client, current = api_client
    current["user"] = _user(UserRole.ADMIN, "admin-live")
    await _insert_candidate(
        isolated_db,
        "cand-live-synth",
        full_name="Synthetic Live Candidate",
        current_title="Finance Manager",
        current_company="Synthetic Corp",
        years_experience=7,
    )

    if not os.environ.get("EMERGENT_LLM_KEY"):
        pytest.skip("EMERGENT_LLM_KEY ausente: live classify no disponible en este entorno")

    response = await client.post("/api/atlas/classify/cand-live-synth")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("confidence_score"), (float, int))
    assert payload.get("industry") is None or isinstance(payload.get("industry"), str)
