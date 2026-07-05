"""
Backend tests for the DASHBOARD OPERATIVO + JOB ASSIGNMENTS + NOTES block.

Covered:
- POST /api/auth/login
- GET  /api/dashboard/operational (kpis + jobs_board + recent_activity + action_inbox + charts)
- POST /api/candidates/{id}/assign-job (create assignment)
- GET  /api/jobs/{job_id}/assignments
- 2 assignments per candidate, stage independence
- PUT  /api/candidates/{cand}/job-assignments/{job} (stage transition, invalid stage rejection)
- PUT stage=placed -> restriction_info.category=placed_by_humaniq, is_placed True
- POST /api/candidates/{id}/notes + GET /api/candidates/{id}/notes
- KPI placed_candidates_count increments after placement
- entity_name is missing in candidate_created activity log (regresión menor)
- Cleanup: soft-delete test candidate, delete test job, unrestrict if needed

Uses MongoDB Atlas real DB — TEST_ prefix + cleanup fixture is critical.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

API = f"{BASE_URL}/api"
ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASS = "Humaniq123"

VALID_STAGES = {"new", "reviewing", "qualified", "ready_to_send",
                "submitted", "interviewed", "offer", "placed", "discarded"}


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data and data["access_token"]
    return data["access_token"]


@pytest.fixture(scope="session")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def taxonomy(hdr):
    """Fetch one industry / functional_area key to build a valid job."""
    r = requests.get(f"{API}/admin/industries", headers=hdr, timeout=15)
    industries = r.json() if r.status_code == 200 else []
    r = requests.get(f"{API}/admin/functional-areas", headers=hdr, timeout=15)
    fas = r.json() if r.status_code == 200 else []

    def _key(item):
        if isinstance(item, dict):
            return item.get("key") or item.get("id") or item.get("name_es")
        return None

    ind_key = _key(industries[0]) if industries else "manufacturing"
    fa_key = _key(fas[0]) if fas else "supply_chain"
    return {"industry": ind_key, "functional_area": fa_key}


@pytest.fixture(scope="session")
def test_data(hdr, taxonomy):
    """Create 2 TEST_ candidates + 2 TEST_ jobs and yield them for tests.
       Full cleanup at teardown (soft-delete candidates, unrestrict, delete jobs)."""
    created_candidates = []
    created_jobs = []

    # candidate 1
    r = requests.post(f"{API}/candidates", headers=hdr, json={
        "full_name": "TEST_Assign Candidate One",
        "email": f"test_assign_one_{int(time.time())}@example.com",
        "country": "México",
    }, timeout=20)
    assert r.status_code in (200, 201), f"cand1 create failed: {r.status_code} {r.text}"
    cand1 = r.json()
    created_candidates.append(cand1["id"])

    # candidate 2 (for concurrency of same candidate to 2 jobs, we only need 1 cand + 2 jobs)
    # keep cand2 to test simple assignment
    r = requests.post(f"{API}/candidates", headers=hdr, json={
        "full_name": "TEST_Assign Candidate Two",
        "email": f"test_assign_two_{int(time.time())}@example.com",
        "country": "México",
    }, timeout=20)
    assert r.status_code in (200, 201)
    cand2 = r.json()
    created_candidates.append(cand2["id"])

    # job 1
    job_payload_a = {
        "title": "TEST_Assign Job A",
        "company": "TEST Co A",
        "industry": taxonomy["industry"],
        "functional_area": taxonomy["functional_area"],
        "seniority": "senior",
        "min_experience": 0,
    }
    r = requests.post(f"{API}/jobs", headers=hdr, json=job_payload_a, timeout=20)
    assert r.status_code in (200, 201), f"job A create failed: {r.status_code} {r.text}"
    job_a = r.json()
    created_jobs.append(job_a["id"])

    job_payload_b = {
        "title": "TEST_Assign Job B",
        "company": "TEST Co B",
        "industry": taxonomy["industry"],
        "functional_area": taxonomy["functional_area"],
        "seniority": "senior",
        "min_experience": 0,
    }
    r = requests.post(f"{API}/jobs", headers=hdr, json=job_payload_b, timeout=20)
    assert r.status_code in (200, 201), f"job B create failed: {r.status_code} {r.text}"
    job_b = r.json()
    created_jobs.append(job_b["id"])

    yield {
        "cand1_id": cand1["id"],
        "cand2_id": cand2["id"],
        "job_a_id": job_a["id"],
        "job_b_id": job_b["id"],
    }

    # ---------- Cleanup ----------
    for cid in created_candidates:
        try:
            # Unrestrict if it was placed (multipart form)
            requests.post(f"{API}/candidates/{cid}/unrestrict",
                          headers=hdr, files={"notes": (None, "TEST cleanup")}, timeout=15)
        except Exception:
            pass
        try:
            requests.delete(f"{API}/candidates/{cid}", headers=hdr, timeout=15)
        except Exception:
            pass

    for jid in created_jobs:
        try:
            requests.delete(f"{API}/jobs/{jid}", headers=hdr, timeout=15)
        except Exception:
            pass


# ---------- Tests ----------

# ===== AUTH =====
class TestAuth:
    def test_login_ok(self, token):
        assert isinstance(token, str) and len(token) > 20


# ===== DASHBOARD OPERATIVO =====
class TestOperationalDashboard:
    def test_dashboard_structure(self, hdr):
        r = requests.get(f"{API}/dashboard/operational", headers=hdr, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("kpis", "jobs_board", "recent_activity", "action_inbox", "charts"):
            assert key in data, f"missing key {key}"

        kpis = data["kpis"]
        for k in ("total_candidates_active", "total_jobs_active",
                  "candidates_this_month", "avg_days_jobs_open",
                  "pending_classifications_count", "placed_candidates_count"):
            assert k in kpis
            assert isinstance(kpis[k], (int, float))

        # jobs_board shape
        assert isinstance(data["jobs_board"], list)
        if data["jobs_board"]:
            j = data["jobs_board"][0]
            for k in ("id", "title", "days_open", "candidates_by_stage",
                      "assigned_total", "health"):
                assert k in j
            assert j["health"] in ("red", "yellow", "green")

        # action_inbox shape
        ainbox = data["action_inbox"]
        for k in ("pending_classifications", "my_unassigned_candidates", "my_stale_jobs"):
            assert k in ainbox

        # charts shape
        charts = data["charts"]
        for k in ("by_functional_area", "new_by_week", "by_caliber"):
            assert k in charts


# ===== ASSIGNMENTS =====
class TestAssignments:
    def test_assign_candidate_to_job(self, hdr, test_data):
        cid, jid = test_data["cand2_id"], test_data["job_a_id"]
        r = requests.post(f"{API}/candidates/{cid}/assign-job",
                          headers=hdr, json={"job_id": jid}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("assignment", {}).get("stage") == "new"
        assert d["assignment"]["job_id"] == jid

        # Verify appears in job assignments listing
        r = requests.get(f"{API}/jobs/{jid}/assignments", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        ass = r.json()
        assert ass["job_id"] == jid
        ids = [a["candidate_id"] for a in ass["assignments"]]
        assert cid in ids

    def test_duplicate_assignment_conflict(self, hdr, test_data):
        cid, jid = test_data["cand2_id"], test_data["job_a_id"]
        # same as above → 409 expected
        r = requests.post(f"{API}/candidates/{cid}/assign-job",
                          headers=hdr, json={"job_id": jid}, timeout=15)
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"

    def test_same_candidate_two_jobs_independent_stages(self, hdr, test_data):
        cid = test_data["cand1_id"]
        job_a, job_b = test_data["job_a_id"], test_data["job_b_id"]

        # assign to both
        for j in (job_a, job_b):
            r = requests.post(f"{API}/candidates/{cid}/assign-job",
                              headers=hdr, json={"job_id": j}, timeout=15)
            assert r.status_code == 200, r.text

        # move assignment on job_a to 'reviewing'
        r = requests.put(f"{API}/candidates/{cid}/job-assignments/{job_a}",
                         headers=hdr, json={"stage": "reviewing"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["stage"] == "reviewing"

        # Verify: job_a listing → cand1 stage 'reviewing', job_b listing → cand1 stage 'new'
        ass_a = requests.get(f"{API}/jobs/{job_a}/assignments", headers=hdr, timeout=15).json()
        ass_b = requests.get(f"{API}/jobs/{job_b}/assignments", headers=hdr, timeout=15).json()

        row_a = next(a for a in ass_a["assignments"] if a["candidate_id"] == cid)
        row_b = next(a for a in ass_b["assignments"] if a["candidate_id"] == cid)
        assert row_a["stage"] == "reviewing", f"expected reviewing, got {row_a['stage']}"
        assert row_b["stage"] == "new", (
            f"STAGE LEAK: cand assignment to jobB changed to {row_b['stage']} when jobA was moved"
        )

    def test_invalid_stage_rejected(self, hdr, test_data):
        cid, jid = test_data["cand1_id"], test_data["job_a_id"]
        r = requests.put(f"{API}/candidates/{cid}/job-assignments/{jid}",
                         headers=hdr, json={"stage": "invalido_xyz"}, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}"


# ===== PLACEMENT + RESTRICTION =====
class TestPlacement:
    def test_place_creates_restriction_and_kpi_moves(self, hdr, test_data):
        cid = test_data["cand1_id"]
        job_a = test_data["job_a_id"]

        # Baseline KPI
        base = requests.get(f"{API}/dashboard/operational",
                            headers=hdr, timeout=30).json()["kpis"]["placed_candidates_count"]

        r = requests.put(f"{API}/candidates/{cid}/job-assignments/{job_a}",
                         headers=hdr, json={"stage": "placed"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["stage"] == "placed"

        # Fetch candidate → is_restricted True + restriction_info.category=placed_by_humaniq
        r = requests.get(f"{API}/candidates/{cid}", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        cand = r.json()
        assert cand.get("is_restricted") is True, "is_restricted should be True after placed"
        info = cand.get("restriction_info") or {}
        assert info.get("category") == "placed_by_humaniq", info
        assert info.get("job_id") == job_a

        # candidate_is_placed reflected in job assignments listing
        ass_a = requests.get(f"{API}/jobs/{job_a}/assignments", headers=hdr, timeout=15).json()
        row_a = next(a for a in ass_a["assignments"] if a["candidate_id"] == cid)
        assert row_a["is_placed"] is True

        # KPI incremented
        after = requests.get(f"{API}/dashboard/operational",
                             headers=hdr, timeout=30).json()["kpis"]["placed_candidates_count"]
        assert after >= base + 1, f"placed KPI didn't move: before={base} after={after}"


# ===== NOTES =====
class TestNotes:
    def test_add_and_get_note(self, hdr, test_data):
        cid = test_data["cand2_id"]

        # add note (Form field)
        r = requests.post(f"{API}/candidates/{cid}/notes",
                          headers=hdr, data={"note_text": "TEST nota operativa"}, timeout=15)
        assert r.status_code == 200, r.text

        # list notes
        r = requests.get(f"{API}/candidates/{cid}/notes", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["candidate_id"] == cid
        assert d["total"] >= 1
        assert any("TEST nota operativa" in (n.get("note") or "") for n in d["notes"])


# ===== ACTIVITY LOG REGRESSION =====
class TestActivityLogEntityName:
    """The activity feed shows 'creó al candidato entidad' — this test proves
    that candidate_created logs are missing entity_name / user_name."""

    def test_candidate_created_log_has_entity_name(self, hdr, test_data):
        # Create fresh candidate and inspect the dashboard recent_activity
        r = requests.post(f"{API}/candidates", headers=hdr, json={
            "full_name": "TEST_ActivityLog Candidate",
            "email": f"test_activity_{int(time.time())}@example.com",
            "country": "México",
        }, timeout=15)
        assert r.status_code in (200, 201)
        new_id = r.json()["id"]

        time.sleep(1)
        dash = requests.get(f"{API}/dashboard/operational", headers=hdr, timeout=30).json()
        entry = next((e for e in dash["recent_activity"]
                      if e.get("action") == "candidate_created" and e.get("entity_id") == new_id), None)
        assert entry is not None, "candidate_created log not present in recent_activity"

        # Cleanup
        requests.delete(f"{API}/candidates/{new_id}", headers=hdr, timeout=15)

        # This is the actual regression assert (main-agent-visible bug)
        assert entry.get("entity_name"), (
            "candidate_created activity log MISSING entity_name → "
            "frontend renders 'creó al candidato entidad'. "
            "Fix: create_candidate() at server.py:482 must call log_activity() with entity_name=full_name."
        )
        assert entry.get("user_name"), (
            "candidate_created activity log MISSING user_name → "
            "backend server.py:482 inserts activity_logs directly without user_name."
        )
