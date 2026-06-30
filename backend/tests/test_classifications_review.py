"""
Tests for Classification Review feature (Bandeja Por Revisar).
Endpoints:
  - GET  /api/atlas/classifications/pending
  - GET  /api/atlas/classifications/pending/count
  - POST /api/atlas/classifications/bulk-approve
  - POST /api/atlas/classifications/correct/{candidate_id}
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")
EMAIL = "test_utf8@atlas.com"
PASSWORD = "Humaniq123"


@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token
    return token


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ----- GET /api/atlas/classifications/pending -----

class TestPendingClassifications:
    def test_pending_returns_200_and_schema(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("candidates", "total", "page", "limit", "pages"):
            assert key in data, f"Missing key {key} in response: {data.keys()}"
        assert isinstance(data["candidates"], list)
        assert isinstance(data["total"], int)

    def test_pending_filters_low_confidence(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        candidates = r.json()["candidates"]
        # Every candidate returned must have confidence_score < 0.75
        for c in candidates:
            cs = c.get("confidence_score")
            assert cs is not None, f"Missing confidence_score on {c.get('id')}"
            assert cs < 0.75, f"Candidate {c.get('id')} has cs={cs} (>=0.75)"

    def test_pending_pagination(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending?page=1&limit=2", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["limit"] == 2
        assert len(data["candidates"]) <= 2

    def test_pending_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending", timeout=15)
        assert r.status_code in (401, 403)


# ----- GET /api/atlas/classifications/pending/count -----

class TestPendingCount:
    def test_count_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending/count", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_count_matches_pending_total(self, auth_headers):
        r1 = requests.get(f"{BASE_URL}/api/atlas/classifications/pending/count", headers=auth_headers, timeout=30)
        r2 = requests.get(f"{BASE_URL}/api/atlas/classifications/pending?limit=100", headers=auth_headers, timeout=30)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["count"] == r2.json()["total"], \
            f"count={r1.json()['count']} vs total={r2.json()['total']}"


# ----- POST /api/atlas/classifications/bulk-approve -----

class TestBulkApprove:
    def test_bulk_approve_empty_list_returns_400(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/atlas/classifications/bulk-approve",
            json={"candidate_ids": []},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 400

    def test_bulk_approve_invalid_id(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/atlas/classifications/bulk-approve",
            json={"candidate_ids": ["TEST_invalid_id_zzz"]},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["approved_count"] == 0
        assert data["total_requested"] == 1
        assert data["errors"] and data["errors"][0]["id"] == "TEST_invalid_id_zzz"

    def test_bulk_approve_real_candidate_persists(self, auth_headers):
        # Pick a real pending candidate
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending?limit=1", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        candidates = r.json()["candidates"]
        if not candidates:
            pytest.skip("No pending candidates available for approval test")
        candidate_id = candidates[0]["id"]
        proposed_fa = candidates[0]["proposed_classification"].get("functional_area")

        # Approve
        r2 = requests.post(
            f"{BASE_URL}/api/atlas/classifications/bulk-approve",
            json={"candidate_ids": [candidate_id]},
            headers=auth_headers,
            timeout=30,
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["approved_count"] == 1
        assert body["total_requested"] == 1

        # Verify persistence via candidate detail
        r3 = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers, timeout=30)
        assert r3.status_code == 200, r3.text
        cand = r3.json()
        assert cand.get("ai_classification", {}).get("approved_by_recruiter") is True
        if proposed_fa:
            assert cand.get("functional_area") == proposed_fa, \
                f"functional_area not applied: {cand.get('functional_area')} vs {proposed_fa}"


# ----- POST /api/atlas/classifications/correct/{candidate_id} -----

class TestCorrectClassification:
    def test_correct_invalid_id_returns_404(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/atlas/classifications/correct/TEST_no_such_id",
            json={"functional_area": "finance"},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code in (400, 404)

    def test_correct_real_candidate_persists(self, auth_headers):
        # Find any candidate with ai_classification to correct
        r = requests.get(f"{BASE_URL}/api/atlas/classifications/pending?limit=5", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        candidates = r.json()["candidates"]
        if not candidates:
            pytest.skip("No pending candidates available for correction test")
        candidate_id = candidates[-1]["id"]  # Use last to avoid collision with approval test

        payload = {
            "industry": "technology",
            "functional_area": "it_technology",
            "seniority": "mid",
            "tags": ["TEST_corrected"],
        }
        r2 = requests.post(
            f"{BASE_URL}/api/atlas/classifications/correct/{candidate_id}",
            json=payload,
            headers=auth_headers,
            timeout=30,
        )
        assert r2.status_code == 200, r2.text

        # Verify persistence
        r3 = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers, timeout=30)
        assert r3.status_code == 200
        cand = r3.json()
        assert cand.get("functional_area") == "it_technology"
        assert cand.get("industry") == "technology"
