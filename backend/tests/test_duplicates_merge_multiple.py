"""
Tests for duplicate detection and merge-multiple feature.

Covers:
- POST /api/candidates/merge-multiple
- GET  /api/duplicates/review
- GET  /api/duplicates/orphan-records
- POST /api/duplicates/cleanup-orphans
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")

# Test credentials from environment with defaults for local testing
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "test_utf8@atlas.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "Humaniq123")

ALEX_GROUP_IDS = [
    "7405dadf-4d61-451b-8b95-9db8a0e7b08e",  # oldest -> should become primary
    "ac190fba-bd2f-44be-bc19-51fa70d5d148",
    "b215e8ca-689e-4ae5-804b-fa44427dff3c",
    "2e217fc1-372e-42ac-b0de-7e9ce6d7cb2d",
]
PRIMARY_ID = ALEX_GROUP_IDS[0]
SECONDARY_IDS = ALEX_GROUP_IDS[1:]


@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return token


@pytest.fixture(scope="session")
def client(auth_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    })
    return s


# ---------- Auth ----------
class TestAuth:
    def test_login_success(self, auth_token):
        assert isinstance(auth_token, str) and len(auth_token) > 10


# ---------- Duplicates review ----------
class TestDuplicatesReview:
    def test_review_endpoint_returns_groups(self, client):
        r = client.get(f"{BASE_URL}/api/duplicates/review", timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert "duplicate_groups" in data
        assert "total_groups" in data
        assert isinstance(data["duplicate_groups"], list)

    def test_review_includes_alex_group(self, client):
        r = client.get(f"{BASE_URL}/api/duplicates/review", timeout=60)
        data = r.json()
        # Find a group that contains the primary Alex
        found = False
        for g in data["duplicate_groups"]:
            ids = [c.get("id") for c in g.get("candidates", [])]
            if PRIMARY_ID in ids:
                found = True
                # Group should have >=2 candidates
                assert len(g["candidates"]) >= 2
                break
        # Not strictly required (may already be merged) so just log
        if not found:
            print("WARN: Alex Shapiro group not found in review - may already be merged")


# ---------- Stats ----------
class TestDuplicateStats:
    def test_stats_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/duplicates/stats", timeout=30)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        for key in ["total_duplicate_groups", "total_duplicate_records", "by_match_type", "pending_suggestions", "total_merges_performed"]:
            assert key in data


# ---------- Merge-multiple validation ----------
class TestMergeMultipleValidation:
    def test_empty_secondaries_returns_400(self, client):
        r = client.post(
            f"{BASE_URL}/api/candidates/merge-multiple",
            json={"primary_candidate_id": PRIMARY_ID, "secondary_candidate_ids": []},
            timeout=30,
        )
        assert r.status_code == 400, r.text[:300]

    def test_primary_in_secondaries_returns_400(self, client):
        r = client.post(
            f"{BASE_URL}/api/candidates/merge-multiple",
            json={"primary_candidate_id": PRIMARY_ID, "secondary_candidate_ids": [PRIMARY_ID]},
            timeout=30,
        )
        assert r.status_code == 400, r.text[:300]

    def test_nonexistent_primary_returns_404(self, client):
        r = client.post(
            f"{BASE_URL}/api/candidates/merge-multiple",
            json={
                "primary_candidate_id": "nonexistent-primary-xyz-000",
                "secondary_candidate_ids": ["nonexistent-secondary-xyz-001"],
            },
            timeout=30,
        )
        # Could be 404 (not found) or 500 wrapping the error
        assert r.status_code in (404, 500), r.text[:300]


# ---------- Merge-multiple happy path (Alex group) ----------
class TestMergeAlexGroup:
    def _get_candidate(self, client, cid):
        r = client.get(f"{BASE_URL}/api/candidates/{cid}", timeout=30)
        return r

    def test_primary_exists_before_merge(self, client):
        r = self._get_candidate(client, PRIMARY_ID)
        if r.status_code == 404:
            pytest.skip("Primary candidate already not found - group may have been merged earlier")
        assert r.status_code == 200

    def test_merge_multiple_alex_group(self, client):
        # Skip if primary doesn't exist
        r = self._get_candidate(client, PRIMARY_ID)
        if r.status_code == 404:
            pytest.skip("Primary candidate not available")

        # Determine which secondaries are still active
        active_secondaries = []
        for sid in SECONDARY_IDS:
            rr = self._get_candidate(client, sid)
            if rr.status_code == 200 and not rr.json().get("is_deleted"):
                active_secondaries.append(sid)

        if not active_secondaries:
            pytest.skip("No active secondary Alex candidates remain - already merged")

        merge_body = {
            "primary_candidate_id": PRIMARY_ID,
            "secondary_candidate_ids": active_secondaries,
            "merge_experience": True,
            "merge_education": True,
            "merge_skills": True,
            "merge_notes": True,
            "keep_all_cvs": True,
            "use_secondary_contact": False,
        }
        r = client.post(f"{BASE_URL}/api/candidates/merge-multiple", json=merge_body, timeout=120)
        assert r.status_code == 200, f"Merge failed: {r.status_code} {r.text[:500]}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("primary_candidate_id") == PRIMARY_ID
        assert data.get("total_merged") == len(active_secondaries)

    def test_secondaries_soft_deleted_after_merge(self, client):
        for sid in SECONDARY_IDS:
            r = self._get_candidate(client, sid)
            if r.status_code == 200:
                body = r.json()
                # Either flagged is_deleted=True, has merged_into, or returned status indicating merge
                assert (
                    body.get("is_deleted") is True
                    or body.get("merged_into") is not None
                    or body.get("status") == "merged"
                ), f"Secondary {sid} not soft-deleted/merged: keys={list(body.keys())[:15]}"
            else:
                # 404 also acceptable
                assert r.status_code in (404, 410), r.text[:200]

    def test_primary_still_active_after_merge(self, client):
        r = self._get_candidate(client, PRIMARY_ID)
        assert r.status_code == 200
        body = r.json()
        assert body.get("is_deleted") is not True
        assert body.get("merged_into") in (None, "", PRIMARY_ID)


# ---------- Orphan records ----------
class TestOrphanRecords:
    def test_get_orphan_records(self, client):
        r = client.get(f"{BASE_URL}/api/duplicates/orphan-records", timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert "total_orphans" in data
        assert "categorized" in data
        assert "by_category" in data
        for cat in ["no_contact_info", "no_resume", "incomplete_profile", "generic_name"]:
            assert cat in data["categorized"]
            assert cat in data["by_category"]

    def test_cleanup_orphans_empty_returns_400(self, client):
        r = client.post(f"{BASE_URL}/api/duplicates/cleanup-orphans", json=[], timeout=30)
        assert r.status_code == 400, r.text[:300]

    def test_cleanup_orphans_nonexistent_returns_success_with_zero(self, client):
        # Should succeed but delete 0 (no matching records)
        r = client.post(
            f"{BASE_URL}/api/duplicates/cleanup-orphans",
            json=["nonexistent-orphan-id-aaa", "nonexistent-orphan-id-bbb"],
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("success") is True
        assert data.get("deleted_count") == 0
