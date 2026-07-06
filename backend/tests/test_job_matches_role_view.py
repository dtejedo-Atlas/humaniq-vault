"""
Test that GET /api/jobs/{id}/matches returns the SAME structure regardless of role.
The role-based filtering is 100% frontend. Backend must return identical fields:
match_percentage, v3_hms, v3_action, strengths, risks for both admin and recruiter.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASSWORD = "Humaniq123"
RECRUITER_EMAIL = "dtejedo@gmail.com"
RECRUITER_PASSWORD = "Humaniq2026!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return data["access_token"], data.get("user", {}).get("role")


@pytest.fixture(scope="module")
def admin_token():
    tok, role = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert role in ("admin", "super_admin"), f"Expected admin role, got {role}"
    return tok


@pytest.fixture(scope="module")
def recruiter_token():
    tok, role = _login(RECRUITER_EMAIL, RECRUITER_PASSWORD)
    assert role == "recruiter", f"Expected recruiter, got {role}"
    return tok


@pytest.fixture(scope="module")
def job_id_with_matches(admin_token):
    """Find a job with results (Director de Operaciones or Director de Finanzas)."""
    r = requests.get(
        f"{BASE_URL}/api/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    jobs = r.json()
    if isinstance(jobs, dict):
        jobs = jobs.get("results") or jobs.get("jobs") or []
    # Prefer specific known jobs
    target_titles = ("Director de Operaciones", "Director de Finanzas")
    for j in jobs:
        if any(t.lower() in (j.get("title") or "").lower() for t in target_titles):
            return j["id"]
    # Fallback: first active job
    for j in jobs:
        if j.get("status") == "active":
            return j["id"]
    pytest.skip("No jobs available")


def _get_matches(token, job_id):
    r = requests.get(
        f"{BASE_URL}/api/jobs/{job_id}/matches?limit=50&threshold=50",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    return r


def test_admin_matches_response_shape(admin_token, job_id_with_matches):
    r = _get_matches(admin_token, job_id_with_matches)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "results" in body
    assert "matched_candidates" in body
    if body["results"]:
        cand = body["results"][0]
        for field in ("candidate_id", "candidate_name", "match_percentage", "strengths", "risks"):
            assert field in cand, f"Missing {field} in admin match response"


def test_recruiter_matches_response_shape(recruiter_token, job_id_with_matches):
    r = _get_matches(recruiter_token, job_id_with_matches)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "results" in body
    if body["results"]:
        cand = body["results"][0]
        for field in ("candidate_id", "candidate_name", "match_percentage", "strengths", "risks"):
            assert field in cand, f"Missing {field} in recruiter match response"


def test_admin_and_recruiter_same_structure(admin_token, recruiter_token, job_id_with_matches):
    """Both roles should get the same keys per candidate result."""
    ra = _get_matches(admin_token, job_id_with_matches)
    rr = _get_matches(recruiter_token, job_id_with_matches)
    assert ra.status_code == 200
    assert rr.status_code == 200
    a_body = ra.json()
    r_body = rr.json()
    if not a_body["results"] or not r_body["results"]:
        pytest.skip("Job has no matched candidates to compare")
    a_keys = set(a_body["results"][0].keys())
    r_keys = set(r_body["results"][0].keys())
    # Both must expose the enrichment fields v3_hms, v3_action (may be None) and standard fields
    for critical in ("match_percentage", "strengths", "risks"):
        assert critical in a_keys and critical in r_keys, f"Field {critical} missing from one role"
    # v3_hms / v3_action expected keys in enriched response
    for v3f in ("v3_hms", "v3_action"):
        assert v3f in a_keys, f"admin missing {v3f}"
        assert v3f in r_keys, f"recruiter missing {v3f}"
    # Structural parity
    diff = a_keys.symmetric_difference(r_keys)
    assert not diff, f"Response keys differ between roles: {diff}"


def test_matching_engine_version_env():
    """MATCHING_ENGINE_VERSION should still be 'compare' in backend/.env."""
    env_path = "/app/backend/.env"
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "MATCHING_ENGINE_VERSION=compare" in content, "MATCHING_ENGINE_VERSION is not 'compare'"
