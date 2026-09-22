"""Isolated review-classification API tests using temporary local MongoDB."""

import asyncio
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

import server  # noqa: E402
from models import User, UserRole  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture
async def isolated_db():
    """Temporary LOCAL Mongo DB for endpoint tests (never shared Atlas data)."""
    mongo_url = os.environ.get("MONGO_URL")
    assert mongo_url, "MONGO_URL no configurada"

    db_name = f"test_class_review_v2_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[db_name]

    original_db = server.db
    original_bp_db = server.background_processor.db
    server.db = test_db
    server.background_processor.db = test_db

    await test_db.industries.insert_many([
        {"key": "test_industry_one", "name_es": "Industria Test 1"},
        {"key": "test_industry_two", "name_es": "Industria Test 2"},
    ])
    await test_db.functional_areas.insert_many([
        {"key": "test_area_one", "name_es": "Área Test 1"},
        {"key": "test_area_two", "name_es": "Área Test 2"},
    ])

    try:
        yield test_db
    finally:
        server.db = original_db
        server.background_processor.db = original_bp_db
        server.app.dependency_overrides.clear()
        await client.drop_database(db_name)
        client.close()


@pytest.fixture
async def api_client(isolated_db):
    """ASGI client with auth dependency override."""
    fake_user = User(id="test-admin", email="test-admin@example.com", name="Test Admin", role=UserRole.ADMIN)

    def _override_user():
        return fake_user

    server.app.dependency_overrides[server.get_current_user] = _override_user
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _insert_candidate(db, candidate_id: str, **extra):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": candidate_id,
        "full_name": f"TEST {candidate_id}",
        "industry": None,
        "functional_area": None,
        "seniority": None,
        "years_experience": None,
        "notes": [{"id": "n1", "note": "keep", "created_by": "u", "created_at": now}],
        "job_assignments": [{"job_id": "j1", "stage": "new"}],
        "ai_classification": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    doc.update(extra)
    await db.candidates.insert_one(doc)


# Manual patch behavior


async def test_manual_patch_saves_fields_preserves_metadata_and_stays_pending(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        "cand-save",
        ai_classification={
            "industry": "test_industry_one",
            "functional_area": "test_area_one",
            "seniority": "junior",
            "confidence_score": 0.41,
            "approved_by_recruiter": False,
            "source": "atlas_ai",
            "classified_at": "2025-01-01T00:00:00+00:00",
            "extra_meta": "keep",
        },
    )

    assert (await api_client.patch("/api/atlas/classifications/manual/cand-save", json={"industry": "test_industry_two"})).status_code == 200
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-save", json={"functional_area": "test_area_two"})).status_code == 200
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-save", json={"seniority": "manager"})).status_code == 200
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-save", json={"years_experience": 0})).status_code == 200
    clear_resp = await api_client.patch("/api/atlas/classifications/manual/cand-save", json={"industry": None})
    assert clear_resp.status_code == 200
    assert clear_resp.json()["industry"] is None

    doc = await isolated_db.candidates.find_one({"id": "cand-save"}, {"_id": 0})
    ai = doc["ai_classification"]
    assert doc["years_experience"] == 0
    assert doc["notes"][0]["note"] == "keep"
    assert doc["job_assignments"][0]["job_id"] == "j1"
    assert ai["confidence_score"] == 0.41
    assert ai["approved_by_recruiter"] is False
    assert ai["source"] == "atlas_ai"
    assert ai["extra_meta"] == "keep"
    assert ai["manual_fields"]["years_experience"] == 0

    pending_ids = await api_client.get("/api/atlas/classifications/pending/ids")
    assert pending_ids.status_code == 200
    assert "cand-save" in pending_ids.json()["candidate_ids"]


async def test_manual_patch_handles_ai_null_and_concurrent_merge(api_client, isolated_db):
    await _insert_candidate(isolated_db, "cand-concurrent", ai_classification=None)

    async def patch_industry():
        return await api_client.patch("/api/atlas/classifications/manual/cand-concurrent", json={"industry": "test_industry_one"})

    async def patch_area():
        return await api_client.patch("/api/atlas/classifications/manual/cand-concurrent", json={"functional_area": "test_area_one"})

    r1, r2 = await asyncio.gather(patch_industry(), patch_area())
    assert r1.status_code == 200
    assert r2.status_code == 200

    doc = await isolated_db.candidates.find_one({"id": "cand-concurrent"}, {"_id": 0, "industry": 1, "functional_area": 1, "ai_classification": 1})
    assert doc["industry"] == "test_industry_one"
    assert doc["functional_area"] == "test_area_one"
    assert doc["ai_classification"]["approved_by_recruiter"] is False


async def test_manual_patch_validation_and_rejections(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        "cand-approved",
        ai_classification={"industry": "test_industry_one", "functional_area": "test_area_one", "seniority": "senior", "approved_by_recruiter": True},
    )
    await _insert_candidate(isolated_db, "cand-deleted", is_deleted=True)
    await _insert_candidate(isolated_db, "cand-valid", ai_classification={"approved_by_recruiter": False})

    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={})).status_code == 400
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-missing", json={"industry": "test_industry_one"})).status_code == 404
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-deleted", json={"industry": "test_industry_one"})).status_code == 404
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-approved", json={"industry": "test_industry_one"})).status_code == 409

    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={"industry": "not_catalog"})).status_code == 422
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={"years_experience": -1})).status_code == 422
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={"years_experience": 1.5})).status_code == 422
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={"years_experience": True})).status_code == 422
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={"years_experience": "1"})).status_code == 422
    assert (await api_client.patch("/api/atlas/classifications/manual/cand-valid", json={"unknown_field": "x"})).status_code == 422


# Approval + queue predicate behavior


async def test_approval_flows_bulk_mixed_and_pending_predicate_consistent(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        "cand-approve-ok",
        years_experience=12,
        ai_classification={
            "industry": "test_industry_one",
            "functional_area": "test_area_one",
            "seniority": "manager",
            "confidence_score": 0.52,
            "approved_by_recruiter": False,
        },
    )
    await _insert_candidate(
        isolated_db,
        "cand-bulk-good",
        ai_classification={
            "industry": "test_industry_two",
            "functional_area": "test_area_two",
            "seniority": "senior",
            "confidence_score": 0.20,
            "approved_by_recruiter": False,
        },
    )
    await _insert_candidate(
        isolated_db,
        "cand-bulk-bad",
        ai_classification={
            "industry": "not_catalog",
            "functional_area": "test_area_two",
            "seniority": "senior",
            "confidence_score": 0.20,
            "approved_by_recruiter": False,
        },
    )
    await _insert_candidate(isolated_db, "cand-no-classification", ai_classification=None)

    single_ok = await api_client.post("/api/atlas/approve-classification/cand-approve-ok")
    assert single_ok.status_code == 200

    single_bad = await api_client.post("/api/atlas/approve-classification/cand-no-classification")
    assert single_bad.status_code == 422

    bulk = await api_client.post(
        "/api/atlas/classifications/bulk-approve",
        json={"candidate_ids": ["cand-bulk-good", "cand-bulk-bad", "cand-missing"]},
    )
    assert bulk.status_code == 200
    payload = bulk.json()
    assert payload["approved_count"] == 1
    assert payload["total_requested"] == 3
    assert len(payload["errors"] or []) == 2

    good_doc = await isolated_db.candidates.find_one({"id": "cand-bulk-good"}, {"_id": 0, "ai_classification.approved_by_recruiter": 1})
    bad_doc = await isolated_db.candidates.find_one({"id": "cand-bulk-bad"}, {"_id": 0, "ai_classification.approved_by_recruiter": 1})
    assert good_doc["ai_classification"]["approved_by_recruiter"] is True
    assert bad_doc["ai_classification"]["approved_by_recruiter"] is False

    page_1 = await api_client.get("/api/atlas/classifications/pending", params={"page": 1, "limit": 2})
    page_2 = await api_client.get("/api/atlas/classifications/pending", params={"page": 2, "limit": 2})
    ids_resp = await api_client.get("/api/atlas/classifications/pending/ids")
    count_resp = await api_client.get("/api/atlas/classifications/pending/count")
    assert page_1.status_code == 200 and page_2.status_code == 200 and ids_resp.status_code == 200 and count_resp.status_code == 200

    paginated_ids = [c["id"] for c in page_1.json()["candidates"] + page_2.json()["candidates"]]
    all_ids = ids_resp.json()["candidate_ids"]
    assert set(paginated_ids) == set(all_ids)
    assert ids_resp.json()["total"] == count_resp.json()["count"] == page_1.json()["total"]


async def test_latest_batch_scoped_to_user_and_serializable(api_client, isolated_db):
    none_resp = await api_client.get("/api/candidates/upload-batches/latest")
    assert none_resp.status_code == 200
    assert none_resp.json() == {"batch_id": None}

    now = datetime.now(timezone.utc).isoformat()
    await isolated_db.upload_batches.insert_many([
        {"batch_id": "batch-a", "user_id": "another-user", "total_files": 1, "jobs": [], "created_at": now, "submission_complete": True},
        {"batch_id": "batch-b", "user_id": "test-admin", "total_files": 2, "jobs": [], "created_at": now, "submission_complete": True},
    ])

    latest = await api_client.get("/api/candidates/upload-batches/latest")
    assert latest.status_code == 200
    assert latest.json()["batch_id"] == "batch-b"
