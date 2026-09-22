"""Layer2 CAPA2 isolated tests: chronology, conditional pass, cache/idempotency, recheck routes, upload worker."""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

import classification_refinement as cr  # noqa: E402
import cv_recheck_service as recheck_service  # noqa: E402
import server  # noqa: E402
from background_processor import ProcessingJob  # noqa: E402
from classification_evidence import EmploymentEvidence, employment_timeline  # noqa: E402
from classification_refinement import classify_with_refinement, second_pass  # noqa: E402
from models import User, UserRole  # noqa: E402
from server import process_cv_job  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture
async def isolated_db():
    """Temporary LOCAL Mongo DB for CAPA2 tests."""
    mongo_url = os.environ.get("MONGO_URL")
    assert mongo_url, "MONGO_URL no configurada"

    db_name = f"test_layer2_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    original_db = server.db
    original_bp_db = server.background_processor.db
    server.db = db
    server.background_processor.db = db
    try:
        yield db
    finally:
        server.db = original_db
        server.background_processor.db = original_bp_db
        server.app.dependency_overrides.clear()
        await client.drop_database(db_name)
        client.close()


@pytest.fixture
async def asgi_client(isolated_db):
    user = User(id="u-admin", email="u-admin@example.com", name="Admin", role=UserRole.ADMIN)

    def override_user():
        return user

    server.app.dependency_overrides[server.get_current_user] = override_user
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def _e(company, start=None, end=None, ongoing=False, industry=None, evidence="quote"):
    return EmploymentEvidence(company=company, start=start, end=end, ongoing=ongoing, industry=industry, evidence=evidence)


# Chronology


def test_timeline_overlap_floor_last_decade_split_and_ongoing():
    today = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jobs = [
        _e("A", start="2020-01", end="2020-12", industry="tech"),
        _e("B", start="2020-06", end="2021-05", industry="manufacturing"),
        _e("C", start="2010-01", end="2012-12", industry="finance"),
        _e("D", start="2025-01", ongoing=True, industry="tech"),
    ]
    result = employment_timeline(jobs, today=today)

    # 12 + 12 + 36 + 13 - overlap(7 months in 2020) = 66 unique months
    assert result["experience_months"] == 66
    assert result["years_experience"] == 5  # floor
    assert result["industry"] == "tech"  # old finance period should not dominate recent decade
    assert result["industry_months_last_decade"]["tech"] > result["industry_months_last_decade"]["manufacturing"]


def test_timeline_tie_unknown_and_invalid_dates_are_not_invented():
    today = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jobs = [
        _e("Tie1", start="2024-01", end="2024-12", industry="tech"),
        _e("Tie2", start="2024-01", end="2024-12", industry="manufacturing"),
        _e("UnknownOnly", start="2025-01", end="2025-06", industry=None),
        _e("MissingStart", start=None, end="2020-01", industry="tech"),
        _e("Future", start="2099-01", end="2100-01", industry="tech"),
        _e("Reversed", start="2022-06", end="2022-01", industry="tech"),
    ]
    result = employment_timeline(jobs, today=today)

    assert result["industry"] is None
    assert result["industry_ambiguous"] is True
    assert set(result["undated_employers"]) >= {"MissingStart", "Future", "Reversed"}
    assert result["years_experience"] >= 1


async def test_second_pass_years_zero_only_with_explicit_no_experience_statement(monkeypatch, isolated_db):
    async def fake_model(*args, **kwargs):
        return json.dumps({
            "industry": None,
            "functional_area": "operations",
            "seniority": "entry",
            "confidence_score": 0.8,
            "field_confidence": {"industry": 0.8, "functional_area": 0.8, "seniority": 0.8, "years_experience": 0.8},
            "employments": [],
            "no_work_experience": True,
            "reasoning": "ok",
            "uncertainty": []
        })

    monkeypatch.setattr(cr, "_model_response", fake_model)
    implicit = await second_pass(
        isolated_db,
        "Este curriculum incluye información académica y habilidades, además de lenguaje profesional amplio y extenso, "
        "pero no declara explícitamente ausencia total de experiencia laboral previa."
    )
    explicit = await second_pass(
        isolated_db,
        "Este curriculum incluye información académica, habilidades, proyectos y contexto adicional suficiente; "
        "declara explícitamente sin experiencia laboral previa y busca primer empleo profesional."
    )

    assert implicit["years_experience"] is None
    assert explicit["years_experience"] == 0


# Conditional wrapper


async def test_wrapper_bypasses_second_pass_for_high_confidence_and_years_zero(monkeypatch, isolated_db):
    calls = {"second": 0}

    async def fake_first(self, candidate, text):
        return {
            "industry": "manufacturing",
            "functional_area": "operations",
            "seniority": "manager",
            "confidence_score": 0.91,
            "suggested_tags": ["kept"],
        }

    async def fake_second(*args, **kwargs):
        calls["second"] += 1
        return {}

    async def fake_catalogs(_db):
        return ({"manufacturing": "Manufacturing"}, {"operations": "Operations"})

    monkeypatch.setattr(cr.AtlasAIService, "classify_candidate", fake_first)
    monkeypatch.setattr(cr, "second_pass", fake_second)
    monkeypatch.setattr(cr, "catalogs", fake_catalogs)

    readable_text = "Experiencia profesional sólida en operaciones, liderazgo, estrategia, resultados, procesos, equipos, mejora continua y gestión internacional durante muchos años en distintos contextos empresariales."
    out = await classify_with_refinement(isolated_db, {"years_experience": 0, "country": "México"}, readable_text)
    assert out["review_status"] == "classified"
    assert out["years_experience"] == 0
    assert out["suggested_tags"] == ["kept"]
    assert calls["second"] == 0


@pytest.mark.parametrize(
    "first,years",
    [
        ({"industry": "manufacturing", "functional_area": "operations", "seniority": "manager", "confidence_score": 0.74}, 10),
        ({"industry": "invalid", "functional_area": "operations", "seniority": "manager", "confidence_score": 0.9}, 10),
        ({"industry": "manufacturing", "functional_area": "operations", "seniority": "manager", "confidence_score": 0.9}, None),
    ],
)
async def test_wrapper_triggers_one_second_pass_when_required(monkeypatch, isolated_db, first, years):
    calls = {"second": 0}

    async def fake_first(self, candidate, text):
        return {**first, "suggested_tags": ["first-tag"]}

    async def fake_second(*args, **kwargs):
        calls["second"] += 1
        return {
            "industry": "manufacturing",
            "functional_area": "operations",
            "seniority": "manager",
            "years_experience": 12,
            "confidence_score": 0.8,
            "review_status": "classified",
            "review_message": "",
            "suggested_tags": [],
        }

    async def fake_catalogs(_db):
        return ({"manufacturing": "Manufacturing"}, {"operations": "Operations"})

    monkeypatch.setattr(cr.AtlasAIService, "classify_candidate", fake_first)
    monkeypatch.setattr(cr, "second_pass", fake_second)
    monkeypatch.setattr(cr, "catalogs", fake_catalogs)

    readable_text = "Experiencia profesional sólida en operaciones, liderazgo, estrategia, resultados, procesos, equipos, mejora continua y gestión internacional durante muchos años en distintos contextos empresariales."
    out = await classify_with_refinement(isolated_db, {"years_experience": years, "country": "México"}, readable_text)
    assert calls["second"] == 1
    assert out["suggested_tags"] == ["first-tag"]  # keeps first tags


async def test_wrapper_fallback_on_second_pass_failure(monkeypatch, isolated_db):
    async def fake_first(self, candidate, text):
        return {
            "industry": "manufacturing",
            "functional_area": "operations",
            "seniority": "manager",
            "confidence_score": 0.88,
            "suggested_tags": ["from-first"],
        }

    async def fake_catalogs(_db):
        return ({"manufacturing": "Manufacturing"}, {"operations": "Operations"})

    async def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cr.AtlasAIService, "classify_candidate", fake_first)
    monkeypatch.setattr(cr, "catalogs", fake_catalogs)
    monkeypatch.setattr(cr, "second_pass", boom)

    readable_text = "Experiencia profesional sólida en operaciones, liderazgo, estrategia, resultados, procesos, equipos, mejora continua y gestión internacional durante muchos años en distintos contextos empresariales."
    out = await classify_with_refinement(isolated_db, {"years_experience": None, "country": "México"}, readable_text)
    assert out["review_status"] == "pending_review"
    assert out["confidence_score"] <= 0.74
    assert out["suggested_tags"] == ["from-first"]


# Second-pass cache/idempotency and evidence checks


async def test_second_pass_full_text_not_truncated_cache_reuse_and_company_filter(monkeypatch, isolated_db):
    await isolated_db.company_classification_cache.insert_many([
        {"_id": "1", "name": "Microsoft", "country": "México", "industry": "technology", "company_size": "multinacional_global", "basis": "model_knowledge"},
        {"_id": "2", "name": "Empresa Fantasma", "country": "México", "industry": "manufacturing", "company_size": "mediana", "basis": "cv_context"},
    ])
    seen = {"calls": 0, "text_len": 0, "companies": []}

    async def fake_model(text, industries, areas, cached_companies, reference_date):
        seen["calls"] += 1
        seen["text_len"] = len(text)
        seen["companies"] = cached_companies
        return json.dumps({
            "industry": "technology",
            "functional_area": "operations",
            "seniority": "manager",
            "confidence_score": 0.91,
            "field_confidence": {"industry": 0.91, "functional_area": 0.91, "seniority": 0.91, "years_experience": 0.91},
            "employments": [{
                "company": "Microsoft",
                "title": "Operations Manager",
                "industry": "technology",
                "company_size": "multinacional_global",
                "company_basis": "model_knowledge",
                "start": "2020-01",
                "end": "2021-01",
                "ongoing": False,
                "evidence": "Microsoft Operations Manager 2020-01 a 2021-01"
            }],
            "no_work_experience": False,
            "reasoning": "ok",
            "uncertainty": []
        })

    monkeypatch.setattr(cr, "_model_response", fake_model)

    long_text = ("Microsoft Operations Manager 2020-01 a 2021-01. " * 120) + ("x" * 3200)
    first = await second_pass(isolated_db, long_text, country="México")
    second = await second_pass(isolated_db, long_text, country="México")

    assert seen["text_len"] == len(long_text)
    assert seen["calls"] == 1
    assert second["cache_hit"] is True
    assert [entry["name"] for entry in seen["companies"]] == ["Microsoft"]
    assert "_id" not in first


async def test_second_pass_concurrent_duplicate_requests_join_single_call(monkeypatch, isolated_db):
    calls = {"n": 0}

    async def slow_model(*args, **kwargs):
        calls["n"] += 1
        await asyncio.sleep(0.4)
        return json.dumps({
            "industry": "technology",
            "functional_area": "operations",
            "seniority": "manager",
            "confidence_score": 0.9,
            "field_confidence": {"industry": 0.9, "functional_area": 0.9, "seniority": 0.9, "years_experience": 0.9},
            "employments": [],
            "no_work_experience": False,
            "reasoning": "ok",
            "uncertainty": []
        })

    monkeypatch.setattr(cr, "_model_response", slow_model)
    text = "CV synthetic concurrency text with enough alpha words for readability and no ambiguity." * 10
    a, b = await asyncio.gather(second_pass(isolated_db, text), second_pass(isolated_db, text))
    assert calls["n"] == 1
    assert {a.get("cache_hit"), b.get("cache_hit")} == {False, True}


async def test_second_pass_failed_auto_retry_policy_max_two(monkeypatch, isolated_db):
    calls = {"n": 0}

    async def always_fail(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("llm failure")

    monkeypatch.setattr(cr, "_model_response", always_fail)
    text = "Texto suficiente para pasar legibilidad en una segunda pasada fallida." * 10

    with pytest.raises(Exception):
        await second_pass(isolated_db, text, retry_failed=False)
    with pytest.raises(ValueError, match="no se repite automáticamente"):
        await second_pass(isolated_db, text, retry_failed=False)
    with pytest.raises(Exception):
        await second_pass(isolated_db, text, retry_failed=True)
    with pytest.raises(ValueError, match="no se repite automáticamente"):
        await second_pass(isolated_db, text, retry_failed=True)
    assert calls["n"] == 2


async def test_second_pass_quote_year_validation_and_unknown_company_not_inferred(monkeypatch, isolated_db):
    async def fake_model(*args, **kwargs):
        return json.dumps({
            "industry": "technology",
            "functional_area": "operations",
            "seniority": "manager",
            "confidence_score": 0.95,
            "field_confidence": {"industry": 0.95, "functional_area": 0.95, "seniority": 0.95, "years_experience": 0.95},
            "employments": [{
                "company": "Empresa Desconocida",
                "title": "Manager",
                "industry": "technology",
                "company_size": "mediana",
                "company_basis": "unknown",
                "start": "2019-01",
                "end": "2020-01",
                "ongoing": False,
                "evidence": "cita inexistente en cv"
            }],
            "no_work_experience": False,
            "reasoning": "ok",
            "uncertainty": []
        })

    monkeypatch.setattr(cr, "_model_response", fake_model)
    text = (
        "CV con texto real suficiente, muy extenso y legible para segunda pasada, "
        "con múltiples frases de experiencia, responsabilidades, logros y contexto empresarial, "
        "pero sin la cita exacta pedida en la respuesta modelada."
    )
    out = await second_pass(isolated_db, text)
    job = out["second_pass"]["employments"][0]
    assert job["industry"] is None
    assert job["start"] is None and job["end"] is None
    assert any("Fechas sin cita verificable" in msg for msg in out["second_pass"]["uncertainty"])


# CV recheck routes/service + upload worker


async def test_recheck_routes_enqueue_dedupe_status_and_owner_scope(asgi_client, isolated_db):
    now = datetime.now(timezone.utc).isoformat()
    await isolated_db.cv_recheck_batches.insert_many([
        {"batch_id": "other-batch", "user_id": "other-user", "candidate_ids": ["x"], "status": "completed", "created_at": now},
        {"batch_id": "my-old-batch", "user_id": "u-admin", "candidate_ids": ["y", "z"], "status": "completed", "created_at": now},
    ])
    await isolated_db.cv_recheck_jobs.insert_many([
        {"batch_id": "my-old-batch", "candidate_id": "y", "status": "completed", "review_status": "classified", "confidence_score": 0.8},
        {"batch_id": "my-old-batch", "candidate_id": "z", "status": "failed", "message": "fail"},
    ])

    # enqueue dedupe
    start = await asgi_client.post("/api/atlas/classifications/recheck", json={"candidate_ids": ["c1", "c1", "c2"]})
    assert start.status_code == 202
    assert start.json()["total"] == 2

    # owner-scoped latest
    latest = await asgi_client.get("/api/atlas/classifications/rechecks/latest")
    assert latest.status_code == 200
    assert latest.json()["batch_id"] is not None

    progress = await asgi_client.get("/api/atlas/classifications/rechecks/my-old-batch")
    assert progress.status_code == 200
    data = progress.json()
    assert data["completed"] == 1 and data["failed"] == 1
    assert data["is_complete"] is True


async def test_recheck_service_uses_active_cv_version_and_manual_capture_preserves_existing(monkeypatch, isolated_db):
    now = datetime.now(timezone.utc).isoformat()
    cid = "cand-recheck-1"
    await isolated_db.candidates.insert_one({
        "id": cid,
        "full_name": "Test Candidate",
        "country": "México",
        "industry": "manufacturing",
        "functional_area": "operations",
        "seniority": "manager",
        "years_experience": 7,
        "tags": ["keep-tag"],
        "notes": [{"note": "keep"}],
        "job_assignments": [{"job_id": "j1", "stage": "new"}],
        "resume_files": [{"id": "old", "file_path": "uploads/resumes/old.pdf", "file_type": "application/pdf", "upload_date": now}],
        "ai_classification": {"approved_by_recruiter": False, "manual_fields": {"years_experience": 9}},
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    })
    await isolated_db.cv_versions.insert_one({
        "id": "v2",
        "candidate_id": cid,
        "file_key": "uploads/resumes/current.pdf",
        "file_name": "current.pdf",
        "file_type": "application/pdf",
        "is_current": True,
        "is_active": True,
    })

    seen = {"key": None}

    def fake_download(reference):
        seen["key"] = reference["key"]
        return b"pdf-bytes"

    def fake_extract(raw, file_type):
        return {"text": "texto suficiente", "text_chars": 200, "readable": True, "pages": [], "warnings": []}

    async def fake_second(*args, **kwargs):
        return {
            "industry": None,
            "functional_area": None,
            "seniority": None,
            "years_experience": None,
            "confidence_score": 0,
            "review_status": "manual_capture",
            "review_message": "manual",
            "cache_hit": False,
        }

    monkeypatch.setattr(recheck_service, "download_original", fake_download)
    monkeypatch.setattr(recheck_service.DocumentParser, "extract_with_details", fake_extract)
    monkeypatch.setattr(recheck_service, "second_pass", fake_second)

    out = await recheck_service.recheck_candidate(isolated_db, cid)
    assert seen["key"] == "uploads/resumes/current.pdf"
    assert out["review_status"] == "manual_capture"

    saved = await isolated_db.candidates.find_one({"id": cid}, {"_id": 0})
    # preserve old fields on manual_capture
    assert saved["industry"] == "manufacturing"
    assert saved["functional_area"] == "operations"
    assert saved["seniority"] == "manager"
    assert saved["years_experience"] == 7
    assert saved["notes"][0]["note"] == "keep"
    assert saved["job_assignments"][0]["job_id"] == "j1"
    assert saved["tags"] == ["keep-tag"]
    assert saved["created_at"] == now


async def test_recheck_candidate_rejects_human_approved_and_detects_cv_version_change(monkeypatch, isolated_db):
    now = datetime.now(timezone.utc).isoformat()
    cid = "cand-recheck-2"
    await isolated_db.candidates.insert_one({
        "id": cid,
        "full_name": "Approved Candidate",
        "country": "México",
        "resume_files": [{"id": "a", "file_path": "uploads/resumes/a.pdf", "file_type": "application/pdf", "upload_date": now}],
        "ai_classification": {"approved_by_recruiter": True},
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    })
    with pytest.raises(ValueError, match="ya fue aprobada manualmente"):
        await recheck_service.recheck_candidate(isolated_db, cid)

    cid2 = "cand-recheck-3"
    await isolated_db.candidates.insert_one({
        "id": cid2,
        "full_name": "Changing CV",
        "country": "México",
        "resume_files": [{"id": "r1", "file_path": "uploads/resumes/r1.pdf", "file_type": "application/pdf", "upload_date": now}],
        "ai_classification": {"approved_by_recruiter": False},
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    })

    counter = {"n": 0}

    async def fake_current_resume(db, candidate):
        counter["n"] += 1
        if counter["n"] == 1:
            return {"key": "uploads/resumes/r1.pdf", "type": "pdf", "version": "v1"}
        return {"key": "uploads/resumes/r2.pdf", "type": "pdf", "version": "v2"}

    monkeypatch.setattr(recheck_service, "current_resume", fake_current_resume)
    monkeypatch.setattr(recheck_service, "download_original", lambda ref: b"x")
    monkeypatch.setattr(recheck_service.DocumentParser, "extract_with_details", lambda raw, t: {"text": "cv", "text_chars": 100, "readable": True, "pages": [], "warnings": []})
    monkeypatch.setattr(recheck_service, "second_pass", lambda *a, **k: asyncio.sleep(0, result={"industry": "technology", "functional_area": "operations", "seniority": "manager", "years_experience": 5, "confidence_score": 0.8, "review_status": "classified", "review_message": "", "cache_hit": False, "second_pass": {"cache_key": "k1"}}))

    with pytest.raises(ValueError, match="Cambió la versión activa"):
        await recheck_service.recheck_candidate(isolated_db, cid2)


async def test_upload_worker_unreadable_sets_manual_capture_without_llm_calls(monkeypatch, isolated_db):
    async def should_not_call(*args, **kwargs):
        raise AssertionError("LLM path should not be called for unreadable extraction")

    monkeypatch.setattr(server.DocumentParser, "extract_with_details", lambda *_: {"text": "", "text_chars": 0, "readable": False, "pages": [], "warnings": []})
    monkeypatch.setattr(server.atlas_service, "parse_resume", should_not_call)
    monkeypatch.setattr(server, "classify_with_refinement", should_not_call)
    monkeypatch.setattr(server.atlas_service, "generate_summary", should_not_call)
    monkeypatch.setattr(server.duplicate_detector, "detect_duplicates", lambda *_: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(server.storage_service, "upload_resume", lambda *a, **k: {"storage_path": "uploads/resumes/test.pdf", "content_type": "application/pdf"})
    monkeypatch.setattr(server.embedding_service, "generate_candidate_embedding", lambda *a, **k: asyncio.sleep(0, result=[]))

    job = ProcessingJob(job_id="job1", batch_id="batch1", file_name="scan.pdf", file_size=10)
    result = await process_cv_job(job, b"dummy-bytes", {"user_id": "u-admin", "file_name": "scan.pdf", "content_type": "application/pdf"})

    assert result.get("review_status") == "manual_capture"
    assert any("Requiere captura manual" in warning for warning in result.get("warnings", []))

    doc = await isolated_db.candidates.find_one({"id": result["candidate_id"]}, {"_id": 0, "review_status": 1})
    assert doc["review_status"] == "manual_capture"

    job.review_status = "manual_capture"
    payload = job.to_dict()
    assert payload["review_status"] == "manual_capture"


@pytest.mark.integration_live
async def test_live_claude_smoke_single_synthetic_cv_and_cache(isolated_db):
    """One live synthetic call only; no real candidate text, local cache only."""
    if os.environ.get("RUN_LIVE_CLASSIFICATION_TEST") != "1":
        pytest.skip("Live calls are opt-in: RUN_LIVE_CLASSIFICATION_TEST=1")
    if not os.environ.get("EMERGENT_LLM_KEY"):
        pytest.skip("EMERGENT_LLM_KEY no configurada para smoke live")

    text = (
        "Experiencia laboral:\n"
        "\"Microsoft - Operations Manager - 2019-01 a 2021-06\" liderando equipo nacional.\n"
        "\"Grupo Bimbo - Gerente de Planta - 2020-01 a 2022-12\" responsabilidad de presupuesto y personal.\n"
        "Actualmente disponible para nuevos retos."
    )
    out1 = await second_pass(isolated_db, text, country="México")
    out2 = await second_pass(isolated_db, text, country="México")

    assert "review_status" in out1
    assert out2.get("cache_hit") is True
