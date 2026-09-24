"""Isolated security/permission/quota/CORS regression tests for audit fixes."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

import server  # noqa: E402
from ai_workload_limits import reserve_batch, release_batch, try_cv_slot, wait_cv_slot  # noqa: E402
from background_processor import BackgroundProcessor  # noqa: E402
from cors_config import PreviewAwareCORSMiddleware  # noqa: E402
from models import User, UserRole  # noqa: E402


pytestmark = pytest.mark.anyio


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _user(role: UserRole, user_id: str, name: str = "Test User"):
    return User(id=user_id, email=f"{user_id}@example.com", name=name, role=role)


@pytest.fixture
async def isolated_db():
    """Temporary LOCAL Mongo DB + server.db override (no shared Atlas mutations)."""
    mongo_url = os.environ.get("MONGO_URL")
    assert mongo_url, "MONGO_URL no configurada"

    db_name = f"test_security_fixes_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[db_name]

    original_db = server.db
    original_bp_db = server.background_processor.db
    original_assignment_db = server.assignment_service.db
    server.db = test_db
    server.background_processor.db = test_db
    server.assignment_service.db = test_db

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
    """ASGI client against app with dynamic auth dependency override."""
    current = {"user": _user(UserRole.ADMIN, "admin-1", "Admin")}

    def _override_user():
        return current["user"]

    server.app.dependency_overrides[server.get_current_user] = _override_user

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, current


async def _seed_candidate_job(db, candidate_id="cand-1", job_id="job-1"):
    now = _iso_now()
    await db.candidates.insert_one({
        "id": candidate_id,
        "full_name": "TEST Candidate",
        "industry": "ind-1",
        "functional_area": "fa-1",
        "seniority": "junior",
        "years_experience": 2,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "resume_files": [],
        "ai_classification": {
            "industry": "ind-1",
            "functional_area": "fa-1",
            "seniority": "junior",
            "confidence_score": 0.6,
            "approved_by_recruiter": False,
            "classified_at": now,
            "suggested_tags": [],
        },
    })
    await db.jobs.insert_one({
        "id": job_id,
        "title": "TEST Job",
        "industry": "ind-1",
        "functional_area": "fa-1",
        "seniority": "junior",
        "min_experience": 1,
        "created_by": "admin-1",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })


# Role guards and endpoint access checks


async def test_non_admin_roles_blocked_from_admin_mutations(api_client, isolated_db, monkeypatch):
    """Admin-only mutations must return 403 for recruiter/researcher."""
    client, current = api_client
    await _seed_candidate_job(isolated_db, "cand-guard", "job-guard")

    import cv_recheck_service  # local import for monkeypatch

    monkeypatch.setattr(server.atlas_service, "classify_candidate", lambda *_args, **_kwargs: {
        "industry": "ind-1", "functional_area": "fa-1", "seniority": "junior", "confidence_score": 0.9, "suggested_tags": []
    })
    monkeypatch.setattr(cv_recheck_service, "launch_batch", lambda *_args, **_kwargs: None)

    calls = [
        ("DELETE", "/api/candidates/cand-guard", None),
        ("DELETE", "/api/jobs/job-guard", None),
        ("POST", "/api/atlas/classify/cand-guard", None),
        ("POST", "/api/atlas/approve-classification/cand-guard", None),
        ("POST", "/api/atlas/classifications/bulk-approve", {"candidate_ids": ["cand-guard"]}),
        ("POST", "/api/atlas/classifications/correct/cand-guard", {"industry": "ind-1"}),
        ("POST", "/api/atlas/classifications/recheck", {"candidate_ids": ["cand-guard"]}),
        ("POST", "/api/candidates/retry-processing/cand-guard?reprocess_classification=false&reprocess_embedding=false", None),
        ("POST", "/api/candidates/cand-guard/reclassify-seniority", None),
    ]

    for role, uid in [(UserRole.RECRUITER, "rec-guard"), (UserRole.RESEARCHER, "res-guard")]:
        current["user"] = _user(role, uid)
        for method, url, payload in calls:
            response = await client.request(method, url, json=payload)
            assert response.status_code == 403, f"{role.value} unexpectedly allowed for {method} {url}"

    candidate_still = await isolated_db.candidates.find_one({"id": "cand-guard"}, {"_id": 0, "id": 1})
    job_still = await isolated_db.jobs.find_one({"id": "job-guard"}, {"_id": 0, "id": 1})
    assert candidate_still and candidate_still["id"] == "cand-guard"
    assert job_still and job_still["id"] == "job-guard"


async def test_admin_and_super_admin_not_blocked_by_role_layer(api_client, isolated_db, monkeypatch):
    """Admin/super_admin must pass role guards and reach handlers (non-403)."""
    client, current = api_client
    await _seed_candidate_job(isolated_db, "cand-admin-ok", "job-admin-ok")

    import cv_recheck_service

    async def _fake_classify(*_args, **_kwargs):
        return {
            "industry": "ind-1",
            "functional_area": "fa-1",
            "seniority": "junior",
            "confidence_score": 0.95,
            "suggested_tags": ["test"],
        }

    monkeypatch.setattr(server.atlas_service, "classify_candidate", _fake_classify)
    monkeypatch.setattr(cv_recheck_service, "launch_batch", lambda *_args, **_kwargs: None)

    for role, uid in [(UserRole.ADMIN, "admin-allow"), (UserRole.SUPER_ADMIN, "super-allow")]:
        current["user"] = _user(role, uid)
        checks = [
            await client.post("/api/atlas/classify/cand-admin-ok"),
            await client.post("/api/atlas/approve-classification/cand-admin-ok"),
            await client.post("/api/atlas/classifications/bulk-approve", json={"candidate_ids": ["cand-admin-ok"]}),
            await client.post("/api/atlas/classifications/correct/cand-admin-ok", json={"industry": "ind-1"}),
            await client.post("/api/atlas/classifications/recheck", json={"candidate_ids": ["cand-admin-ok"]}),
            await client.post("/api/candidates/retry-processing/cand-admin-ok?reprocess_classification=false&reprocess_embedding=false"),
            await client.post("/api/candidates/cand-admin-ok/reclassify-seniority"),
            await client.delete("/api/jobs/job-admin-ok"),
        ]
        assert all(resp.status_code != 403 for resp in checks)


async def test_manual_patch_permissions_and_pending_can_edit(api_client, isolated_db):
    """Manual patch: admin or assigned recruiter only; researcher denied even assigned."""
    client, current = api_client
    now = _iso_now()
    await isolated_db.candidates.insert_one({
        "id": "cand-manual",
        "full_name": "Manual Candidate",
        "industry": None,
        "functional_area": None,
        "seniority": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "resume_files": [],
        "ai_classification": {"approved_by_recruiter": False, "confidence_score": 0.3, "classified_at": now},
    })
    await isolated_db.assignments.insert_many([
        {"id": "a1", "candidate_id": "cand-manual", "recruiter_id": "rec-assigned", "status": "active", "assigned_at": now, "assigned_by": "x", "assigned_by_name": "x", "candidate_name": "Manual Candidate", "recruiter_name": "Rec"},
        {"id": "a2", "candidate_id": "cand-manual", "recruiter_id": "res-assigned", "status": "active", "assigned_at": now, "assigned_by": "x", "assigned_by_name": "x", "candidate_name": "Manual Candidate", "recruiter_name": "Res"},
    ])

    current["user"] = _user(UserRole.RECRUITER, "rec-assigned")
    ok = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"years_experience": 3})
    assert ok.status_code == 200

    current["user"] = _user(UserRole.RECRUITER, "rec-other")
    forbidden = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"functional_area": "fa-1"})
    assert forbidden.status_code == 403

    current["user"] = _user(UserRole.RESEARCHER, "res-assigned")
    forbidden_res = await client.patch("/api/atlas/classifications/manual/cand-manual", json={"seniority": "mid"})
    assert forbidden_res.status_code == 403

    pending = await client.get("/api/atlas/classifications/pending")
    assert pending.status_code == 200
    row = next(x for x in pending.json()["candidates"] if x["id"] == "cand-manual")
    assert row["can_edit"] is False


async def test_stage_move_allowed_for_any_recruiter_but_not_researcher(api_client, isolated_db):
    """Any recruiter can move assignment stage; researcher gets 403."""
    client, current = api_client
    now = _iso_now()
    await isolated_db.candidates.insert_one({
        "id": "cand-stage",
        "full_name": "Stage Candidate",
        "job_assignments": [{"job_id": "job-stage", "stage": "new", "assigned_by": "adm", "assigned_at": now, "updated_at": now}],
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "resume_files": [],
    })
    await isolated_db.jobs.insert_one({"id": "job-stage", "title": "Job Stage", "industry": "ind-1", "functional_area": "fa-1", "seniority": "junior", "min_experience": 1, "created_by": "admin", "status": "active", "created_at": now, "updated_at": now})

    current["user"] = _user(UserRole.RECRUITER, "rec-unassigned")
    moved = await client.put("/api/candidates/cand-stage/job-assignments/job-stage", json={"stage": "interviewed"})
    assert moved.status_code == 200

    current["user"] = _user(UserRole.RESEARCHER, "res-blocked")
    blocked = await client.put("/api/candidates/cand-stage/job-assignments/job-stage", json={"stage": "discarded"})
    assert blocked.status_code == 403


# Candidate notes permission and integrity checks


async def test_notes_create_author_is_server_actor_and_validation(api_client, isolated_db):
    """Any authenticated user can create notes; author spoofing not accepted."""
    client, current = api_client
    now = _iso_now()
    await isolated_db.candidates.insert_one({
        "id": "cand-notes",
        "full_name": "Notes Candidate",
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "resume_files": [],
    })

    current["user"] = _user(UserRole.RESEARCHER, "res-note", "Research Name")
    created = await client.post(
        "/api/candidates/cand-notes/notes",
        data={"note_text": "valid note", "created_by_id": "spoofed-user", "created_by": "spoofed-name"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["note"]["created_by_id"] == "res-note"
    assert payload["note"]["created_by"] == "Research Name"
    assert payload["note"]["id"]

    empty = await client.post("/api/candidates/cand-notes/notes", data={"note_text": "   "})
    long_text = await client.post("/api/candidates/cand-notes/notes", data={"note_text": "x" * 10001})
    missing_candidate = await client.post("/api/candidates/404-notes/notes", data={"note_text": "hello"})
    assert empty.status_code == 422
    assert long_text.status_code == 422
    assert missing_candidate.status_code == 404


async def test_notes_edit_delete_only_owner_or_admin_and_not_by_same_name(api_client, isolated_db):
    """Patch/delete: owner by created_by_id or admin/super_admin only."""
    client, current = api_client
    now = _iso_now()
    await isolated_db.candidates.insert_one({
        "id": "cand-notes-ownership",
        "full_name": "Owner Candidate",
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "notes": [{"id": "note-owner", "note": "orig", "created_by": "Same Name", "created_by_id": "owner-1", "created_at": now}],
        "resume_files": [],
    })

    current["user"] = _user(UserRole.RECRUITER, "other-1", "Same Name")
    blocked_patch = await client.patch("/api/candidates/cand-notes-ownership/notes/note-owner", json={"note_text": "hack"})
    blocked_delete = await client.delete("/api/candidates/cand-notes-ownership/notes/note-owner")
    assert blocked_patch.status_code == 403
    assert blocked_delete.status_code == 403

    current["user"] = _user(UserRole.ADMIN, "admin-2", "Admin")
    admin_patch = await client.patch("/api/candidates/cand-notes-ownership/notes/note-owner", json={"note_text": "admin edit"})
    assert admin_patch.status_code == 200
    admin_delete = await client.delete("/api/candidates/cand-notes-ownership/notes/note-owner")
    assert admin_delete.status_code == 200

    no_note = await client.patch("/api/candidates/cand-notes-ownership/notes/missing", json={"note_text": "x"})
    no_candidate = await client.delete("/api/candidates/missing-cand/notes/missing")
    assert no_note.status_code == 404
    assert no_candidate.status_code == 404


async def test_legacy_note_reference_deterministic_read_only_admin_only_edit(api_client, isolated_db):
    """Legacy note without id/author_id exposes deterministic id and only admin can mutate."""
    client, current = api_client
    now = _iso_now()
    legacy_note = {"note": "legacy body", "created_by": "Legacy User", "created_at": now}
    await isolated_db.candidates.insert_one({
        "id": "cand-legacy",
        "full_name": "Legacy Candidate",
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "notes": [legacy_note],
        "resume_files": [],
    })

    current["user"] = _user(UserRole.RECRUITER, "rec-legacy", "Recruiter")
    first_get = await client.get("/api/candidates/cand-legacy")
    second_get = await client.get("/api/candidates/cand-legacy")
    assert first_get.status_code == 200 and second_get.status_code == 200
    id1 = first_get.json()["notes"][0]["id"]
    id2 = second_get.json()["notes"][0]["id"]
    assert id1 == id2 and id1.startswith("legacy-0-")

    doc_after_get = await isolated_db.candidates.find_one({"id": "cand-legacy"}, {"_id": 0, "notes": 1})
    assert "id" not in doc_after_get["notes"][0]

    blocked = await client.patch(f"/api/candidates/cand-legacy/notes/{id1}", json={"note_text": "recruiter edit"})
    assert blocked.status_code == 403

    current["user"] = _user(UserRole.ADMIN, "admin-legacy", "Admin")
    edited = await client.patch(f"/api/candidates/cand-legacy/notes/{id1}", json={"note_text": "admin edit legacy"})
    assert edited.status_code == 200
    updated_doc = await isolated_db.candidates.find_one({"id": "cand-legacy"}, {"_id": 0, "notes": 1})
    assert updated_doc["notes"][0].get("id")
    assert updated_doc["notes"][0].get("created_by_id") in (None, "")


# Quotas and background concurrency checks


async def test_reserve_batch_limits_and_retry_after(isolated_db):
    """1 in turn + 2 waiting; 4th reserve gets 429 with Retry-After."""
    await reserve_batch(isolated_db, "quota-user", "b1", "upload", 10)
    await reserve_batch(isolated_db, "quota-user", "b2", "upload", 10)
    await reserve_batch(isolated_db, "quota-user", "b3", "upload", 10)

    with pytest.raises(Exception) as exc:
        await reserve_batch(isolated_db, "quota-user", "b4", "upload", 10)
    err = exc.value
    assert getattr(err, "status_code", None) == 429
    assert err.headers.get("Retry-After") == "30"

    await release_batch(isolated_db, "quota-user", "b1")
    await release_batch(isolated_db, "quota-user", "b2")
    await release_batch(isolated_db, "quota-user", "b3")


async def test_batch_size_limit_and_duplicate_batch_id_not_duplicated(isolated_db):
    """Batch >50 rejected; same batch_id repeated does not duplicate reservation."""
    with pytest.raises(Exception) as exc:
        await reserve_batch(isolated_db, "size-user", "too-many", "upload", 51)
    assert getattr(exc.value, "status_code", None) == 400

    await reserve_batch(isolated_db, "dup-user", "dup-batch", "upload", 1)
    await reserve_batch(isolated_db, "dup-user", "dup-batch", "upload", 1)
    row = await isolated_db.ai_user_workloads.find_one({"_id": "dup-user"}, {"_id": 0, "batches": 1})
    live_ids = [entry.get("batch_id") for entry in row.get("batches", []) if entry.get("batch_id")]
    assert live_ids.count("dup-batch") == 1
    await release_batch(isolated_db, "dup-user", "dup-batch")


async def test_cv_slots_fifo_and_two_parallel_limit_per_user(isolated_db):
    """Only first queued batch may claim slots; per-user max concurrent lease is 2."""
    await reserve_batch(isolated_db, "slot-user", "first", "upload", 2)
    await reserve_batch(isolated_db, "slot-user", "second", "upload", 2)

    lease1 = await try_cv_slot(isolated_db, "slot-user", "first")
    lease2 = await try_cv_slot(isolated_db, "slot-user", "first")
    lease3 = await try_cv_slot(isolated_db, "slot-user", "first")
    from_second = await try_cv_slot(isolated_db, "slot-user", "second")
    assert lease1 is not None and lease2 is not None
    assert lease3 is None
    assert from_second is None

    await lease1.release()
    await lease2.release()
    await release_batch(isolated_db, "slot-user", "first")
    await release_batch(isolated_db, "slot-user", "second")


async def test_background_processor_50_files_respects_per_user_cv_cap(isolated_db):
    """Simulate 50-CV batch with controlled async worker; observe <=2 concurrent per user."""
    processor = BackgroundProcessor(max_concurrent=3)
    processor.db = isolated_db
    await processor.initialize()

    max_seen = {"u50": 0}
    inflight = {"u50": 0}
    lock = asyncio.Lock()

    async def controlled(job, file_data, file_metadata):
        user_id = file_metadata["user_id"]
        async with lock:
            inflight[user_id] = inflight.get(user_id, 0) + 1
            max_seen[user_id] = max(max_seen.get(user_id, 0), inflight[user_id])
        await asyncio.sleep(0.01)
        async with lock:
            inflight[user_id] -= 1
        return {"status": "success", "candidate_id": f"cand-{job.job_id[:8]}", "errors": [], "warnings": []}

    await processor.start_workers(controlled)
    batch = await processor.create_batch("u50", 50)
    for i in range(50):
        await processor.add_job(batch.batch_id, f"cv-{i}.pdf", f"bytes-{i}".encode(), "application/pdf", "u50")

    await processor.queue.join()
    await processor.finalize_batch(batch.batch_id, [{"file_name": f"cv-{i}.pdf", "status": "queued"} for i in range(50)])
    status = await processor.get_batch_status(batch.batch_id)

    assert status["stats"]["completed"] == 50
    assert status["stats"]["failed"] == 0
    assert max_seen["u50"] <= 2
    processor.workers_running = False


async def test_expired_records_do_not_block_new_reservations(isolated_db):
    """Legacy expired batches/leases should not count as active blockers."""
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    await isolated_db.ai_user_workloads.insert_one({
        "_id": "legacy-user",
        "batches": [{"batch_id": "old", "kind": "upload", "expires_at": past}],
        "leases": [{"token": "old-token", "batch_id": "old", "expires_at": past}],
    })
    await reserve_batch(isolated_db, "legacy-user", "fresh", "upload", 1)
    lease = await wait_cv_slot(isolated_db, "legacy-user", "fresh")
    assert lease is not None
    await lease.release()
    await release_batch(isolated_db, "legacy-user", "fresh")


async def test_note_concurrent_add_returns_409_without_losing_other_note(api_client, isolated_db):
    client, current = api_client
    current['user'] = _user(UserRole.RECRUITER, 'author-race')
    original = {'id': 'note-race', 'note': 'Original', 'created_by': 'Author', 'created_by_id': 'author-race', 'created_at': _iso_now()}
    concurrent = {'id': 'other-note', 'note': 'Concurrent addition', 'created_by': 'Other', 'created_by_id': 'other-author', 'created_at': _iso_now()}
    await isolated_db.candidates.insert_one({'id': 'cand-race', 'notes': [original], 'is_deleted': False})

    class RacingCollection:
        async def find_one(self, *args, **kwargs):
            return await isolated_db.candidates.find_one(*args, **kwargs)

        async def update_one(self, *args, **kwargs):
            await isolated_db.candidates.update_one({'id': 'cand-race'}, {'$push': {'notes': concurrent}})
            return await isolated_db.candidates.update_one(*args, **kwargs)

    class RacingDB:
        candidates = RacingCollection()

        def __getattr__(self, name):
            return getattr(isolated_db, name)

    previous = server.db
    server.db = RacingDB()
    try:
        response = await client.patch('/api/candidates/cand-race/notes/note-race', json={'note_text': 'Replacement'})
        assert response.status_code == 409
    finally:
        server.db = previous
    after = await isolated_db.candidates.find_one({'id': 'cand-race'}, {'_id': 0})
    assert after['notes'] == [original, concurrent]


# Seed + CORS checks


async def test_seed_initial_data_super_admin_only_and_idempotent(api_client, isolated_db):
    """Unauth/recruiter/researcher/admin denied; super_admin seeds once then idempotent."""
    client, current = api_client

    server.app.dependency_overrides.pop(server.get_current_user, None)
    unauth = await client.post("/api/seed/initial-data")
    assert unauth.status_code in (401, 403)

    # Restore override for role checks
    server.app.dependency_overrides[server.get_current_user] = lambda: current["user"]

    for role, uid in [
        (UserRole.RECRUITER, "rec-seed"),
        (UserRole.RESEARCHER, "res-seed"),
        (UserRole.ADMIN, "adm-seed"),
    ]:
        current["user"] = _user(role, uid)
        denied = await client.post("/api/seed/initial-data")
        assert denied.status_code == 403

    current["user"] = _user(UserRole.SUPER_ADMIN, "sup-seed")
    first = await client.post("/api/seed/initial-data")
    second = await client.post("/api/seed/initial-data")
    assert first.status_code == 200
    assert second.status_code == 200
    assert "inicializados" in second.json()["message"].lower() or "ya" in second.json()["message"].lower()


async def test_preview_aware_cors_allows_only_configured_origins_and_proxy_alias(monkeypatch):
    """Preview alias normalizes exact internal proxy origin only; no wildcard/regex origin acceptance."""
    monkeypatch.setenv("CORS_PREVIEW_PUBLIC_ORIGIN", "https://atlas-recruiting-ai.preview.emergentagent.com")
    monkeypatch.setenv("CORS_PREVIEW_PROXY_ORIGIN", "https://atlas-recruiting-ai.cluster-2.preview.emergentcf.cloud")

    app = FastAPI()

    @app.get("/api/auth/me")
    async def fake_auth_me():
        return {"detail": "auth required"}

    app.add_middleware(
        PreviewAwareCORSMiddleware,
        allow_credentials=True,
        allow_origins=[
            "https://atlas-recruiting-ai.emergent.host",
            "https://atlas-recruiting-ai.preview.emergentagent.com",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ok_prod = await client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://atlas-recruiting-ai.emergent.host",
                "Access-Control-Request-Method": "GET",
            },
        )
        ok_preview = await client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://atlas-recruiting-ai.preview.emergentagent.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        alias_preview = await client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://atlas-recruiting-ai.cluster-2.preview.emergentcf.cloud",
                "Access-Control-Request-Method": "GET",
            },
        )
        bad_origin = await client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://security-audit.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )
        lookalike = await client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://atlas-recruiting-ai.cluster-999.preview.emergentcf.cloud",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert ok_prod.status_code == 200
    assert ok_preview.status_code == 200
    assert alias_preview.status_code == 200
    assert ok_prod.headers.get("access-control-allow-origin") == "https://atlas-recruiting-ai.emergent.host"
    assert ok_preview.headers.get("access-control-allow-origin") == "https://atlas-recruiting-ai.preview.emergentagent.com"
    assert alias_preview.headers.get("access-control-allow-origin") == "https://atlas-recruiting-ai.preview.emergentagent.com"
    assert bad_origin.status_code == 400
    assert bad_origin.headers.get("access-control-allow-origin") is None
    assert lookalike.status_code == 400
