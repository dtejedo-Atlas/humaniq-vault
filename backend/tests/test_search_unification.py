"""
Test Search Unification - Atlas Talent Vault
=============================================
Tests that GET /api/candidates?search= and POST /api/search/hybrid return
identical results using the same calibrated hybrid search engine.

Test queries:
- 'director de operaciones' (8 results)
- 'supply chain retail' (2 results)
- 'CFO manufactura' (0 results)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test_utf8@atlas.com"
TEST_PASSWORD = "test123456"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSearchUnification:
    """Tests for unified search across GET /api/candidates and POST /api/search/hybrid"""
    
    def test_director_operaciones_get_candidates(self, auth_headers):
        """Test GET /api/candidates?search=director de operaciones returns 8 results"""
        response = requests.get(
            f"{BASE_URL}/api/candidates",
            params={"search": "director de operaciones"},
            headers=auth_headers
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 8, f"Expected 8 results, got {len(results)}"
        
        # Verify match_score is present in all results
        for candidate in results:
            assert "match_score" in candidate, f"match_score missing for {candidate.get('full_name')}"
            assert isinstance(candidate["match_score"], int), "match_score should be int"
    
    def test_director_operaciones_hybrid_search(self, auth_headers):
        """Test POST /api/search/hybrid?query=director de operaciones returns 8 results"""
        response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "director de operaciones"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data)
        assert len(results) == 8, f"Expected 8 results, got {len(results)}"
        
        # Verify match_score is present
        for candidate in results:
            assert "match_score" in candidate, f"match_score missing for {candidate.get('full_name')}"
    
    def test_director_operaciones_results_match(self, auth_headers):
        """Test that both endpoints return identical results for 'director de operaciones'"""
        # GET /api/candidates
        get_response = requests.get(
            f"{BASE_URL}/api/candidates",
            params={"search": "director de operaciones"},
            headers=auth_headers
        )
        get_results = get_response.json()
        
        # POST /api/search/hybrid
        post_response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "director de operaciones"},
            headers=auth_headers
        )
        post_data = post_response.json()
        post_results = post_data.get("results", post_data)
        
        # Compare counts
        assert len(get_results) == len(post_results), "Result counts don't match"
        
        # Compare candidate IDs and scores
        get_ids = {c["id"]: c["match_score"] for c in get_results}
        post_ids = {c["id"]: c["match_score"] for c in post_results}
        
        assert get_ids == post_ids, "Candidate IDs and scores don't match between endpoints"
    
    def test_supply_chain_retail_get_candidates(self, auth_headers):
        """Test GET /api/candidates?search=supply chain retail returns 2 results"""
        response = requests.get(
            f"{BASE_URL}/api/candidates",
            params={"search": "supply chain retail"},
            headers=auth_headers
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Verify match_score
        for candidate in results:
            assert "match_score" in candidate
    
    def test_supply_chain_retail_hybrid_search(self, auth_headers):
        """Test POST /api/search/hybrid?query=supply chain retail returns 2 results"""
        response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "supply chain retail"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data)
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    
    def test_supply_chain_retail_results_match(self, auth_headers):
        """Test that both endpoints return identical results for 'supply chain retail'"""
        get_response = requests.get(
            f"{BASE_URL}/api/candidates",
            params={"search": "supply chain retail"},
            headers=auth_headers
        )
        get_results = get_response.json()
        
        post_response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "supply chain retail"},
            headers=auth_headers
        )
        post_results = post_response.json().get("results", [])
        
        get_ids = {c["id"]: c["match_score"] for c in get_results}
        post_ids = {c["id"]: c["match_score"] for c in post_results}
        
        assert get_ids == post_ids, "Results don't match between endpoints"
    
    def test_cfo_manufactura_get_candidates(self, auth_headers):
        """Test GET /api/candidates?search=CFO manufactura returns 0 results"""
        response = requests.get(
            f"{BASE_URL}/api/candidates",
            params={"search": "CFO manufactura"},
            headers=auth_headers
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 0, f"Expected 0 results, got {len(results)}"
    
    def test_cfo_manufactura_hybrid_search(self, auth_headers):
        """Test POST /api/search/hybrid?query=CFO manufactura returns 0 results"""
        response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "CFO manufactura"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data)
        assert len(results) == 0, f"Expected 0 results, got {len(results)}"


class TestSearchMetadata:
    """Tests for search metadata in hybrid search response"""
    
    def test_hybrid_search_returns_metadata(self, auth_headers):
        """Test that POST /api/search/hybrid returns search_metadata"""
        response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "director"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "search_metadata" in data, "search_metadata missing from response"
        metadata = data["search_metadata"]
        
        assert "query" in metadata
        assert "use_semantic" in metadata
        assert "semantic_search_active" in metadata
    
    def test_match_breakdown_present(self, auth_headers):
        """Test that match_breakdown is present in search results"""
        response = requests.post(
            f"{BASE_URL}/api/search/hybrid",
            params={"query": "director de operaciones"},
            headers=auth_headers
        )
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        # At least some results should have match_breakdown
        has_breakdown = any("match_breakdown" in c for c in results)
        assert has_breakdown, "No results have match_breakdown"


class TestCandidatesEndpointWithoutSearch:
    """Tests for GET /api/candidates without search parameter"""
    
    def test_get_all_candidates_no_search(self, auth_headers):
        """Test GET /api/candidates without search returns all candidates"""
        response = requests.get(
            f"{BASE_URL}/api/candidates",
            headers=auth_headers
        )
        assert response.status_code == 200
        results = response.json()
        
        # Should return candidates without match_score (no search query)
        assert len(results) > 0, "Should return some candidates"
    
    def test_get_candidates_with_filters_only(self, auth_headers):
        """Test GET /api/candidates with filters but no search"""
        response = requests.get(
            f"{BASE_URL}/api/candidates",
            params={"industry": "manufacturing"},
            headers=auth_headers
        )
        assert response.status_code == 200
        results = response.json()
        
        # All results should have industry = manufacturing
        for candidate in results:
            if candidate.get("industry"):
                assert candidate["industry"] == "manufacturing"
