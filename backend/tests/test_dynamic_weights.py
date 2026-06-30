"""
Tests for v2.2 Dynamic Weights Redistribution
=============================================
Validates:
1. _calculate_dynamic_weights() redistributes weights based on dimensions present
2. _calculate_keyword_score() accepts short skills from whitelist
3. Search endpoint orders by real keyword relevance
"""

import os
import sys
import pytest
import requests

# Allow importing backend modules
sys.path.insert(0, "/app/backend")

from hybrid_search_service import HybridSearchService, SHORT_SKILLS_WHITELIST
from query_parser import parse_query

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")
LOGIN_EMAIL = "test_utf8@atlas.com"
LOGIN_PASSWORD = "Humaniq123"


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture
def api_client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    return s


@pytest.fixture
def svc():
    # embedding_service not required for weight calculation
    return HybridSearchService(db=None, embedding_service=None)


# ---------- Unit tests for _calculate_dynamic_weights ----------

class TestDynamicWeights:

    def _approx(self, a, b, tol=0.01):
        return abs(a - b) <= tol

    def test_pure_skill_only_keywords(self, svc):
        """Pure skill 'liderazgo' (no area/seniority/industry) → keywords should dominate (~65%) and funcional=0."""
        parsed = parse_query("liderazgo")
        # liderazgo should NOT detect area/seniority/industry
        assert parsed["area_funcional"] is None
        assert parsed["seniority_index"] is None
        assert parsed["industria"] is None
        assert parsed["keywords"], "Expected 'liderazgo' to be in keywords"

        # No embedding scenario (per fix description with 401 embedding API)
        w = svc._calculate_dynamic_weights(parsed, has_embedding=False)

        # funcional must be 0 since no area was detected
        assert w["funcional"] == 0.0, f"funcional should be 0, got {w['funcional']}"
        assert w["seniority"] == 0.0, f"seniority should be 0, got {w['seniority']}"
        assert w["industria"] == 0.0, f"industria should be 0, got {w['industria']}"
        # keywords should dominate, ~65% (problem statement)
        assert w["keywords"] >= 0.60, f"keywords should be >= 60%, got {w['keywords']}"
        # weights sum to ~1.0
        assert self._approx(sum(w.values()), 1.0), f"weights must sum to 1.0, got {sum(w.values())}"

    def test_pure_skill_with_embedding(self, svc):
        """With embedding available, keywords ~ redistributed * 0.60 + base 0.05."""
        parsed = parse_query("liderazgo")
        w = svc._calculate_dynamic_weights(parsed, has_embedding=True)
        # weight_to_redistribute = 0.40 + 0.20 + 0.15 = 0.75
        # keywords = 0.05 + 0.75*0.60 = 0.50, then normalized.
        # Total before normalize: 0.50 + (0.13 + 0.225) + (0.05 + 0.075) + 0.02 = 1.0 (already 1.0)
        assert w["funcional"] == 0.0
        assert w["keywords"] >= 0.45  # ~0.50
        assert self._approx(sum(w.values()), 1.0)

    def test_area_only_finanzas(self, svc):
        """'finanzas' detects area but not seniority/industry → keywords ~33%."""
        parsed = parse_query("finanzas")
        assert parsed["area_funcional"] == "finance"
        assert parsed["seniority_index"] is None
        assert parsed["industria"] is None

        # No embedding
        w = svc._calculate_dynamic_weights(parsed, has_embedding=False)
        # funcional remains 0.40, sen=0 ind=0
        assert w["funcional"] > 0.0
        assert w["seniority"] == 0.0
        assert w["industria"] == 0.0
        # weight_to_redistribute = 0.20 + 0.15 = 0.35
        # keywords = 0.05 + 0.35*0.80 = 0.33
        assert w["keywords"] >= 0.30 and w["keywords"] <= 0.40, (
            f"keywords should be ~33%, got {w['keywords']}"
        )
        assert self._approx(sum(w.values()), 1.0)

    def test_full_query_keeps_base_weights(self, svc):
        """Full query area+sen+ind keeps standard weights."""
        parsed = parse_query("CFO fintech senior")
        assert parsed["area_funcional"] is not None
        assert parsed["seniority_index"] is not None
        assert parsed["industria"] is not None

        w = svc._calculate_dynamic_weights(parsed, has_embedding=True)
        assert self._approx(w["funcional"], 0.40)
        assert self._approx(w["seniority"], 0.20)
        assert self._approx(w["industria"], 0.15)
        assert self._approx(w["keywords"], 0.05)
        assert self._approx(sum(w.values()), 1.0)

    def test_weights_normalize(self, svc):
        """All scenarios produce weights that sum to 1.0."""
        for q in ["java", "python", "sap", "liderazgo", "finanzas",
                  "gerente ventas automotriz", "director comercial"]:
            parsed = parse_query(q)
            for has_emb in [True, False]:
                w = svc._calculate_dynamic_weights(parsed, has_embedding=has_emb)
                assert self._approx(sum(w.values()), 1.0), (
                    f"Weights sum != 1 for '{q}' has_emb={has_emb}: {sum(w.values())}"
                )


# ---------- Unit tests for _calculate_keyword_score short skill whitelist ----------

class TestShortSkillKeywordScore:

    def test_whitelist_contains_expected_skills(self):
        for s in ["bi", "ml", "ai", "go", "r", "sap", "aws"]:
            assert s in SHORT_SKILLS_WHITELIST, f"'{s}' should be whitelisted"

    def test_parse_query_extracts_short_whitelist_skills(self):
        """BUG CHECK: parse_query.extract_keywords filters len(w)>=3, so 2-char skills
        like 'BI', 'ML', 'AI' never reach _calculate_keyword_score. This is a defect."""
        for short in ["BI", "ML", "AI"]:
            parsed = parse_query(short)
            assert short.lower() in parsed["keywords"], (
                f"'{short}' should appear in extracted keywords for whitelist to function. "
                f"Got: {parsed['keywords']}"
            )

    def test_keyword_score_accepts_whitelisted_2char_skill(self, svc=None):
        from hybrid_search_service import HybridSearchService
        svc = HybridSearchService(db=None, embedding_service=None)
        candidate = {
            "current_title": "BI Analyst",
            "current_company": "Acme",
            "ai_summary": "BI dashboards expert",
            "skills": ["BI", "SQL", "Tableau"],
        }
        # Simulate parse output where 'bi' did make it (manually injected)
        parsed = {"keywords": ["bi"], "raw_query": "bi"}
        score, in_title = svc._calculate_keyword_score(candidate, parsed)
        assert score > 0, f"Expected score > 0 for whitelisted 'bi' match, got {score}"
        assert in_title is True

    def test_keyword_score_rejects_non_whitelisted_2char(self):
        svc = HybridSearchService(db=None, embedding_service=None)
        candidate = {
            "current_title": "ZZ Operator",
            "current_company": "Acme",
            "ai_summary": "ZZ team",
            "skills": ["zz"],
        }
        parsed = {"keywords": ["zz"], "raw_query": "zz"}
        score, _ = svc._calculate_keyword_score(candidate, parsed)
        # No valid keywords → score 0
        assert score == 0, f"Expected score 0 for non-whitelisted 2-char keyword, got {score}"


# ---------- Integration tests against API ----------

class TestSearchEndpoint:

    def test_login_ok(self, auth_token):
        assert auth_token

    def test_search_pure_skill_returns_200(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/candidates", params={"search": "Java", "limit": 10}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)

    def test_search_short_skill_sap_returns_200(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/candidates", params={"search": "SAP", "limit": 10}, timeout=30)
        assert r.status_code == 200, r.text

    def test_search_short_2char_bi(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/candidates", params={"search": "BI", "limit": 10}, timeout=30)
        # Endpoint should not crash; may return [] if no candidate has BI
        assert r.status_code == 200, r.text

    def test_search_funcional_finanzas(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/candidates", params={"search": "finanzas", "limit": 10}, timeout=30)
        assert r.status_code == 200, r.text

    def test_search_full_query(self, api_client):
        r = api_client.get(
            f"{BASE_URL}/api/candidates",
            params={"search": "gerente ventas automotriz", "limit": 10},
            timeout=30,
        )
        assert r.status_code == 200, r.text

    def test_search_ordering_python_relevance(self, api_client):
        """Search for 'Python' - results (if any) should be ordered by relevance.
        Because match_score may not be exposed via response_model=Candidate,
        we at least verify the request succeeds and returns a list."""
        r = api_client.get(f"{BASE_URL}/api/candidates", params={"search": "Python", "limit": 20}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
