"""Fusión N-a-1: nada se pierde (notas, asignaciones y CV de la ficha absorbida).

Usa Mongo LOCAL aislado. No toca Atlas.
"""
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / '.env')

from duplicate_detector_v2 import CandidateMerger  # noqa: E402
from models import Candidate  # noqa: E402

NOW = datetime.now(timezone.utc)
MERGE_OPTIONS = {"merge_experience": True, "merge_education": True, "merge_skills": True,
                 "merge_notes": True, "keep_all_cvs": True, "use_secondary_contact": False}


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
async def isolated_db():
    mongo_url = os.environ.get('MONGO_URL')
    assert mongo_url, 'MONGO_URL required'
    db_name = f"test_merge_{uuid.uuid4().hex[:10]}"
    client = AsyncIOMotorClient(mongo_url)
    try:
        yield client[db_name]
    finally:
        await client.drop_database(db_name)
        client.close()


def _note(text, author, author_id, days_ago):
    return {"id": str(uuid.uuid4()), "note": text, "created_by": author, "created_by_id": author_id,
            "created_at": (NOW - timedelta(days=days_ago)).isoformat()}


def _candidate(name, cv_name, cv_key, notes, job_ids, skills, email):
    return {
        "id": str(uuid.uuid4()),
        "full_name": name,
        "email": email,
        "status": "new",
        "created_at": NOW.isoformat(),
        "created_by": "user-1",
        "created_by_name": "Reclutadora Uno",
        "skills": skills,
        "notes": notes,
        "job_assignments": [{"job_id": job_id, "stage": "new", "assigned_by": "user-1",
                             "assigned_at": NOW.isoformat()} for job_id in job_ids],
        "resume_files": [{"file_name": cv_name, "file_path": cv_key,
                          "file_type": "application/pdf", "upload_date": NOW.isoformat()}],
    }


@pytest.fixture
async def merged(isolated_db):
    primary = _candidate("Ana Ruiz", "cv_primario.pdf", "resumes/primary/aaa.pdf",
                         [_note("Entrevista inicial muy buena", "Reclutadora Uno", "user-1", 5)],
                         ["job-A"], ["Excel", "SAP"], "ana@uno.com")
    secondary = _candidate("Ana Ruiz", "cv_secundario.pdf", "resumes/secondary/bbb.pdf",
                           [_note("Referencia laboral confirmada", "Reclutador Dos", "user-2", 2),
                            _note("Pretensión salarial 80k", "Reclutador Dos", "user-2", 1)],
                           ["job-B"], ["Power BI"], "ana@dos.com")
    await isolated_db.candidates.insert_many([primary, secondary])
    await isolated_db.assignments.insert_one(
        {"id": str(uuid.uuid4()), "candidate_id": secondary["id"], "recruiter_id": "user-2", "status": "active"})

    merger = CandidateMerger(isolated_db)
    result = await merger.merge_candidates(primary["id"], secondary["id"], MERGE_OPTIONS, "user-9")
    survivor = await isolated_db.candidates.find_one({"id": primary["id"]}, {"_id": 0})
    return {"db": isolated_db, "primary": primary, "secondary": secondary,
            "result": result, "survivor": survivor}


@pytest.mark.anyio
async def test_notas_de_ambas_fichas_se_conservan_como_lista(merged):
    notes = merged["survivor"]["notes"]
    assert isinstance(notes, list)
    assert len(notes) == 3
    assert {note["note"] for note in notes} == {"Entrevista inicial muy buena",
                                                "Referencia laboral confirmada",
                                                "Pretensión salarial 80k"}


@pytest.mark.anyio
async def test_notas_conservan_autor_y_fecha(merged):
    by_text = {note["note"]: note for note in merged["survivor"]["notes"]}
    original = {note["note"]: note for note in merged["secondary"]["notes"]}
    for text, note in original.items():
        assert by_text[text]["created_by"] == note["created_by"]
        assert by_text[text]["created_by_id"] == note["created_by_id"]
        assert by_text[text]["created_at"] == note["created_at"]
        assert by_text[text]["id"] == note["id"]


@pytest.mark.anyio
async def test_ficha_fusionada_sigue_validando_contra_el_modelo(merged):
    candidate = Candidate.model_validate(merged["survivor"])
    assert len(candidate.notes) == 3
    assert all(note.created_by for note in candidate.notes)


@pytest.mark.anyio
async def test_asignaciones_de_vacantes_no_se_pierden(merged):
    job_ids = {assignment["job_id"] for assignment in merged["survivor"]["job_assignments"]}
    assert job_ids == {"job-A", "job-B"}


@pytest.mark.anyio
async def test_asignaciones_de_reclutador_apuntan_al_principal(merged):
    assignment = await merged["db"].assignments.find_one({"recruiter_id": "user-2"}, {"_id": 0})
    assert assignment["candidate_id"] == merged["primary"]["id"]
    assert assignment["migrated_from_merge"] is True


@pytest.mark.anyio
async def test_cv_absorbido_queda_como_version_historica(merged):
    versions = await merged["db"].cv_versions.find(
        {"candidate_id": merged["primary"]["id"]}, {"_id": 0}).sort("version", 1).to_list(10)
    assert [version["file_name"] for version in versions] == ["cv_primario.pdf", "cv_secundario.pdf"]
    original, absorbed = versions
    assert original["is_current"] is True and original["upload_source"] == "original"
    assert absorbed["is_current"] is False and absorbed["upload_source"] == "merge"
    assert absorbed["file_key"] == "resumes/secondary/bbb.pdf"
    assert absorbed["merged_from_candidate_id"] == merged["secondary"]["id"]
    assert absorbed["is_active"] is True


@pytest.mark.anyio
async def test_skills_y_auditoria(merged):
    assert set(merged["survivor"]["skills"]) == {"Excel", "SAP", "Power BI"}
    audit = await merged["db"].merge_audit_log.find_one(
        {"primary_candidate_id": merged["primary"]["id"]}, {"_id": 0})
    assert audit["secondary_candidate_id"] == merged["secondary"]["id"]
    assert any("nota(s)" in entry for entry in audit["merge_log"])
    assert any("versión histórica" in entry for entry in audit["merge_log"])


@pytest.mark.anyio
async def test_ficha_absorbida_queda_marcada_y_recuperable(merged):
    absorbed = await merged["db"].candidates.find_one({"id": merged["secondary"]["id"]}, {"_id": 0})
    assert absorbed["is_deleted"] is True
    assert absorbed["deletion_type"] == "merged"
    assert absorbed["merged_into"] == merged["primary"]["id"]
    assert len(absorbed["notes"]) == 2  # el original sigue intacto para auditoría


@pytest.mark.anyio
async def test_fusion_repetida_no_duplica_notas_ni_cv(merged):
    merger = CandidateMerger(merged["db"])
    await merger.merge_candidates(merged["primary"]["id"], merged["secondary"]["id"],
                                  MERGE_OPTIONS, "user-9")
    survivor = await merged["db"].candidates.find_one({"id": merged["primary"]["id"]}, {"_id": 0})
    assert len(survivor["notes"]) == 3
    assert len(survivor["job_assignments"]) == 2
    versions = await merged["db"].cv_versions.count_documents({"candidate_id": merged["primary"]["id"]})
    assert versions == 2


@pytest.mark.anyio
async def test_cv_heredado_resume_file_key_tambien_se_conserva(isolated_db):
    primary = _candidate("Luis Paz", "cv_vigente.pdf", "resumes/p/1.pdf", [], [], ["SQL"], "luis@a.com")
    secondary = _candidate("Luis Paz", "ignorado.pdf", "resumes/s/2.pdf", [], [], [], "luis@b.com")
    secondary.pop("resume_files")
    secondary["resume_file_key"] = "resumes/legacy/old.pdf"
    secondary["resume_file_name"] = "cv_heredado.pdf"
    await isolated_db.candidates.insert_many([primary, secondary])
    await CandidateMerger(isolated_db).merge_candidates(
        primary["id"], secondary["id"], MERGE_OPTIONS, "user-9")
    versions = await isolated_db.cv_versions.find(
        {"candidate_id": primary["id"]}, {"_id": 0}).sort("version", 1).to_list(10)
    assert [version["file_name"] for version in versions] == ["cv_vigente.pdf", "cv_heredado.pdf"]
    assert versions[1]["file_key"] == "resumes/legacy/old.pdf"


@pytest.mark.anyio
async def test_notas_heredadas_en_texto_no_corrompen_la_lista(isolated_db):
    primary = _candidate("Eva Lira", "cv.pdf", "resumes/p/e.pdf", [], [], [], "eva@a.com")
    secondary = _candidate("Eva Lira", "cv2.pdf", "resumes/s/e.pdf", [], [], [], "eva@b.com")
    secondary["notes"] = "nota heredada en texto plano"
    await isolated_db.candidates.insert_many([primary, secondary])
    result = await CandidateMerger(isolated_db).merge_candidates(
        primary["id"], secondary["id"], MERGE_OPTIONS, "user-9")
    survivor = await isolated_db.candidates.find_one({"id": primary["id"]}, {"_id": 0})
    assert survivor["notes"] == []
    assert any("formato heredado" in entry for entry in result["changes"])
