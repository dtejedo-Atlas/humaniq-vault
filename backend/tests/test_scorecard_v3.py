"""E2E tests for Job Scorecard endpoints and v3 matching engine (FASE 4)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")
JOB_DIRECTOR = "594c8585-fa9a-43c0-af3c-f63ccf7c34ad"  # Director Comercial (executive)
JOB_GERENTE = "1292337a-26da-46dc-98e1-03cea792def0"  # Gerente de Operaciones (manager)


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "test_utf8@atlas.com", "password": "Humaniq123"},
        timeout=30,
    )
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("access_token")
    assert token
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ---------- Scorecard endpoints ----------
class TestScorecardEndpoints:
    def test_put_scorecard_executive(self, headers):
        resp = requests.put(
            f"{BASE_URL}/api/jobs/{JOB_DIRECTOR}/scorecard",
            headers=headers,
            json={"process_type": "executive", "target_company_caliber": "corporativo_nacional"},
            timeout=30,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source"] == "saved"
        assert data["scorecard"]["process_type"] == "executive"
        assert data["scorecard"]["target_company_caliber"] == "corporativo_nacional"

    def test_get_saved_scorecard(self, headers):
        resp = requests.get(f"{BASE_URL}/api/jobs/{JOB_DIRECTOR}/scorecard", headers=headers, timeout=30)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source"] == "saved"
        assert data["scorecard"]["process_type"] == "executive"
        assert data["scorecard"]["target_company_caliber"] == "corporativo_nacional"

    def test_get_derived_scorecard_manager(self, headers):
        resp = requests.get(f"{BASE_URL}/api/jobs/{JOB_GERENTE}/scorecard", headers=headers, timeout=30)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source"] == "derived"
        # manager seniority -> managerial process
        assert data["scorecard"]["process_type"] == "managerial", data["scorecard"]


# ---------- v3 matching endpoint ----------
class TestMatchV3:
    def test_match_v3_compare_mode(self, headers):
        resp = requests.post(
            f"{BASE_URL}/api/jobs/{JOB_DIRECTOR}/match-v3",
            headers=headers,
            timeout=180,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # compare mode returns engine=compare + v3 and v2 blocks
        assert data.get("engine") == "compare", f"engine field: {data.get('engine')}"
        assert "v3" in data
        assert "v2" in data
        v3_results = data["v3"] if isinstance(data["v3"], list) else data["v3"].get("results") or data["v3"].get("matches")
        assert isinstance(v3_results, list) and len(v3_results) > 0, f"v3 results missing: {data['v3']}"
        first = v3_results[0]
        # Check process_type / weights_used / component_breakdown
        assert first.get("process_type") == "executive", f"process_type={first.get('process_type')}"
        weights = first.get("weights_used") or {}
        assert isinstance(weights, dict) and len(weights) == 11, f"weights_used keys={list(weights.keys())}"
        for k in ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ", "CC"]:
            assert k in weights, f"missing weight {k}"
        comps = first.get("component_breakdown") or first.get("components") or {}
        assert isinstance(comps, dict) and len(comps) >= 11, f"components={list(comps.keys())}"
        assert "CC" in comps, f"CC missing in component_breakdown: {list(comps.keys())}"


# ---------- v2 regression ----------
class TestMatchV2Regression:
    def test_match_v2_still_returns_known_candidates(self, headers):
        resp = requests.post(
            f"{BASE_URL}/api/jobs/{JOB_DIRECTOR}/match",
            headers=headers,
            timeout=180,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # collect candidate names from response
        matches = data.get("results") or data.get("matches") or data.get("candidates") or []
        names = []
        for m in matches:
            n = m.get("candidate_name") or m.get("name") or (m.get("candidate") or {}).get("full_name") or ""
            names.append(n.lower())
        joined = " | ".join(names)
        expected = ["omar alberto vega torres", "david armando cisneros figueroa", "ignacio salazar soto"]
        for cand in expected:
            assert cand in joined, f"Expected candidate '{cand}' not in matches. Got: {joined[:500]}"
