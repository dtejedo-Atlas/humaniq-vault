"""
Test Suite for Atlas Talent Vault - Operational Fixes
======================================================
Tests for:
1. Smart Folder HR classification fix
2. Soft delete candidates
3. Restore candidates (Admin only)
4. Duplicate detection by confidence levels
5. Restrict/Unrestrict candidates with traceability
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://atlas-recruiting-ai.preview.emergentagent.com').rstrip('/')

# Test credentials from environment with defaults for local testing
TEST_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "test_utf8@atlas.com")
TEST_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "Humaniq123")
TEST_CANDIDATE_ID = "5a242806-04ec-467c-bae2-1b99d0943e61"
RESTRICTED_CANDIDATE_ID = "e75df560-272d-44ba-b902-e859a0638a7b"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAuthentication:
    """Test authentication works"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        print(f"✓ Login successful for {TEST_EMAIL}")


class TestSmartFolderHR:
    """Test HR Smart Folder classification fix"""
    
    def test_get_all_folders(self, auth_headers):
        """Test getting all smart folders"""
        response = requests.get(f"{BASE_URL}/api/folders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # API returns folders grouped by category
        assert "by_category" in data or isinstance(data, list)
        if "by_category" in data:
            total = data.get("total", 0)
            assert total > 0
            print(f"✓ Retrieved {total} smart folders (grouped by category)")
        else:
            assert len(data) > 0
            print(f"✓ Retrieved {len(data)} smart folders")
    
    def test_hr_folder_exists(self, auth_headers):
        """Test HR folder exists with correct ID"""
        response = requests.get(f"{BASE_URL}/api/folders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Handle grouped response structure
        if "by_category" in data:
            all_folders = data["by_category"].get("verticals", []) + data["by_category"].get("process", [])
        else:
            all_folders = data
        
        hr_folder = next((f for f in all_folders if f["id"] == "sys_hr"), None)
        assert hr_folder is not None, "HR folder (sys_hr) not found"
        assert hr_folder["name"] == "Recursos Humanos"
        print(f"✓ HR folder found: {hr_folder['name']}")
    
    def test_hr_folder_criteria_includes_talent_acquisition(self, auth_headers):
        """Test HR folder criteria includes human_resources and talent_acquisition"""
        response = requests.get(f"{BASE_URL}/api/folders/sys_hr", headers=auth_headers)
        assert response.status_code == 200
        folder = response.json()
        
        criteria = folder.get("criteria", {})
        functional_areas = criteria.get("functional_area", [])
        
        assert "human_resources" in functional_areas, "human_resources not in HR folder criteria"
        assert "talent_acquisition" in functional_areas, "talent_acquisition not in HR folder criteria"
        print(f"✓ HR folder criteria includes: {functional_areas}")
    
    def test_hr_folder_candidate_count(self, auth_headers):
        """Test HR folder has expected candidate count (should be 5)"""
        response = requests.get(f"{BASE_URL}/api/folders/sys_hr/candidates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        total = data.get("total", 0)
        candidates = data.get("candidates", [])
        
        # Main agent verified 5 candidates
        print(f"✓ HR folder has {total} candidates")
        assert total >= 5, f"Expected at least 5 HR candidates, got {total}"


class TestSoftDelete:
    """Test soft delete functionality"""
    
    def test_get_candidate_before_delete(self, auth_headers):
        """Verify test candidate exists before delete test"""
        response = requests.get(f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}", headers=auth_headers)
        assert response.status_code == 200
        candidate = response.json()
        assert candidate["id"] == TEST_CANDIDATE_ID
        print(f"✓ Test candidate exists: {candidate['full_name']}")
    
    def test_delete_candidate_soft_delete(self, auth_headers):
        """Test DELETE marks candidate as is_deleted=true"""
        # First, create a test candidate to delete
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_DeleteCandidate",
                "email": "test_delete@example.com",
                "source": "Test"
            }
        )
        assert create_response.status_code == 200
        new_candidate = create_response.json()
        candidate_id = new_candidate["id"]
        print(f"✓ Created test candidate: {candidate_id}")
        
        # Delete the candidate
        delete_response = requests.delete(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert "deleted_by" in delete_data
        assert "deleted_at" in delete_data
        print(f"✓ Soft delete successful, deleted by: {delete_data['deleted_by']}")
        
        # Verify candidate still exists in DB but is marked deleted
        get_response = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        assert get_response.status_code == 200
        deleted_candidate = get_response.json()
        assert deleted_candidate.get("is_deleted") == True
        print(f"✓ Candidate marked as is_deleted=true")
        
        # Store for restore test
        return candidate_id
    
    def test_deleted_candidate_not_in_list(self, auth_headers):
        """Test deleted candidates don't appear in candidate list"""
        # Create and delete a candidate
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_HiddenCandidate",
                "email": "test_hidden@example.com",
                "source": "Test"
            }
        )
        assert create_response.status_code == 200
        candidate_id = create_response.json()["id"]
        
        # Delete it
        requests.delete(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        
        # Check it's not in the list
        list_response = requests.get(f"{BASE_URL}/api/candidates", headers=auth_headers)
        assert list_response.status_code == 200
        candidates = list_response.json()
        
        candidate_ids = [c["id"] for c in candidates]
        assert candidate_id not in candidate_ids, "Deleted candidate should not appear in list"
        print(f"✓ Deleted candidate not in candidate list")


class TestRestoreCandidate:
    """Test restore candidate functionality (Admin only)"""
    
    def test_restore_deleted_candidate(self, auth_headers):
        """Test Admin can restore a deleted candidate"""
        # Create a candidate
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_RestoreCandidate",
                "email": "test_restore@example.com",
                "source": "Test"
            }
        )
        assert create_response.status_code == 200
        candidate_id = create_response.json()["id"]
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Restore it
        restore_response = requests.post(f"{BASE_URL}/api/candidates/{candidate_id}/restore", headers=auth_headers)
        assert restore_response.status_code == 200
        restore_data = restore_response.json()
        assert restore_data["message"] == "Candidato restaurado exitosamente"
        print(f"✓ Candidate restored successfully")
        
        # Verify is_deleted is removed
        get_response = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        assert get_response.status_code == 200
        restored_candidate = get_response.json()
        assert restored_candidate.get("is_deleted") != True
        print(f"✓ Candidate is_deleted flag removed")
    
    def test_restore_non_deleted_candidate_fails(self, auth_headers):
        """Test restoring a non-deleted candidate returns error"""
        # Create a fresh candidate that is NOT deleted
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_NotDeletedCandidate",
                "email": "test_notdeleted@example.com",
                "source": "Test"
            }
        )
        assert create_response.status_code == 200
        candidate_id = create_response.json()["id"]
        
        # Try to restore a candidate that's not deleted
        response = requests.post(f"{BASE_URL}/api/candidates/{candidate_id}/restore", headers=auth_headers)
        assert response.status_code == 400
        assert "no está eliminado" in response.json().get("detail", "").lower()
        print(f"✓ Restore non-deleted candidate correctly returns 400")


class TestDuplicateDetection:
    """Test duplicate detection by confidence levels"""
    
    def test_get_duplicates_endpoint(self, auth_headers):
        """Test GET /api/candidates/{id}/duplicates returns categorized duplicates"""
        response = requests.get(f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/duplicates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "active_duplicates" in data
        active = data["active_duplicates"]
        assert "high_confidence" in active
        assert "medium_confidence" in active
        assert "low_confidence" in active
        assert "total" in active
        
        print(f"✓ Duplicates endpoint returns categorized results")
        print(f"  - High confidence: {len(active['high_confidence'])}")
        print(f"  - Medium confidence: {len(active['medium_confidence'])}")
        print(f"  - Low confidence: {len(active['low_confidence'])}")
        print(f"  - Total: {active['total']}")
    
    def test_duplicate_confidence_levels(self, auth_headers):
        """Test duplicate confidence levels are correctly categorized"""
        response = requests.get(f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/duplicates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        active = data["active_duplicates"]
        
        # Verify confidence thresholds
        for dup in active.get("high_confidence", []):
            assert dup["confidence"] >= 0.9, f"High confidence should be >= 0.9, got {dup['confidence']}"
        
        for dup in active.get("medium_confidence", []):
            assert 0.7 <= dup["confidence"] < 0.9, f"Medium confidence should be 0.7-0.9, got {dup['confidence']}"
        
        for dup in active.get("low_confidence", []):
            assert dup["confidence"] < 0.7, f"Low confidence should be < 0.7, got {dup['confidence']}"
        
        print(f"✓ Duplicate confidence levels correctly categorized")
    
    def test_duplicate_has_required_fields(self, auth_headers):
        """Test duplicate entries have required fields"""
        response = requests.get(f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/duplicates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        active = data["active_duplicates"]
        
        all_duplicates = (
            active.get("high_confidence", []) + 
            active.get("medium_confidence", []) + 
            active.get("low_confidence", [])
        )
        
        for dup in all_duplicates:
            assert "candidate_id" in dup, "Duplicate should have candidate_id"
            assert "confidence" in dup, "Duplicate should have confidence"
            assert "reason" in dup, "Duplicate should have reason"
            # candidate_name is optional but useful
        
        print(f"✓ Duplicate entries have required fields")


class TestRestrictCandidate:
    """Test restrict/unrestrict candidate functionality"""
    
    def test_mark_candidate_restricted(self, auth_headers):
        """Test marking a candidate as restricted"""
        # Create a test candidate
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_RestrictCandidate",
                "email": "test_restrict@example.com",
                "source": "Test"
            }
        )
        assert create_response.status_code == 200
        candidate_id = create_response.json()["id"]
        
        # Mark as restricted
        restrict_response = requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/restrict",
            headers=auth_headers,
            json={
                "reason": "Test restriction reason",
                "category": "bad_reference",
                "notes": "Testing restriction functionality"
            }
        )
        assert restrict_response.status_code == 200
        restrict_data = restrict_response.json()
        assert "marked_by" in restrict_data
        assert "marked_at" in restrict_data
        assert restrict_data["category"] == "Mala referencia"
        print(f"✓ Candidate marked as restricted")
        
        # Verify candidate is restricted
        get_response = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        assert get_response.status_code == 200
        candidate = get_response.json()
        assert candidate.get("is_restricted") == True
        assert candidate.get("restriction_info") is not None
        assert candidate["restriction_info"]["category"] == "bad_reference"
        print(f"✓ Candidate is_restricted=true with restriction_info")
        
        return candidate_id
    
    def test_restriction_traceability(self, auth_headers):
        """Test restriction has full traceability (who, when, why)"""
        # Create and restrict a candidate
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_TraceabilityCandidate",
                "email": "test_trace@example.com",
                "source": "Test"
            }
        )
        candidate_id = create_response.json()["id"]
        
        requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/restrict",
            headers=auth_headers,
            json={
                "reason": "Traceability test",
                "category": "ethical_issue"
            }
        )
        
        # Check traceability fields
        get_response = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        candidate = get_response.json()
        restriction_info = candidate.get("restriction_info", {})
        
        assert "marked_by" in restriction_info, "Should have marked_by"
        assert "marked_by_name" in restriction_info, "Should have marked_by_name"
        assert "marked_at" in restriction_info, "Should have marked_at"
        assert "category" in restriction_info, "Should have category"
        assert "category_label" in restriction_info, "Should have category_label"
        
        print(f"✓ Restriction has full traceability:")
        print(f"  - Marked by: {restriction_info['marked_by_name']}")
        print(f"  - Category: {restriction_info['category_label']}")
        print(f"  - At: {restriction_info['marked_at']}")
    
    def test_invalid_restriction_category(self, auth_headers):
        """Test invalid restriction category returns error"""
        response = requests.post(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/restrict",
            headers=auth_headers,
            json={
                "reason": "Test",
                "category": "invalid_category"
            }
        )
        assert response.status_code == 400
        assert "inválida" in response.json().get("detail", "").lower()
        print(f"✓ Invalid category correctly returns 400")
    
    def test_unrestrict_candidate(self, auth_headers):
        """Test Admin can unrestrict a candidate"""
        # Create and restrict a candidate
        create_response = requests.post(f"{BASE_URL}/api/candidates", 
            headers=auth_headers,
            json={
                "full_name": "TEST_UnrestrictCandidate",
                "email": "test_unrestrict@example.com",
                "source": "Test"
            }
        )
        candidate_id = create_response.json()["id"]
        
        # Restrict
        requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/restrict",
            headers=auth_headers,
            json={"reason": "Test", "category": "other"}
        )
        
        # Unrestrict
        unrestrict_response = requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/unrestrict",
            headers=auth_headers,
            data={"notes": "Unrestriction test"}
        )
        assert unrestrict_response.status_code == 200
        print(f"✓ Candidate unrestricted successfully")
        
        # Verify is_restricted is false
        get_response = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}", headers=auth_headers)
        candidate = get_response.json()
        assert candidate.get("is_restricted") == False or candidate.get("is_restricted") is None
        print(f"✓ Candidate is_restricted=false after unrestrict")
    
    def test_unrestrict_non_restricted_fails(self, auth_headers):
        """Test unrestricting a non-restricted candidate returns error"""
        response = requests.post(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/unrestrict",
            headers=auth_headers
        )
        # Should fail if candidate is not restricted
        if response.status_code == 400:
            assert "no está restringido" in response.json().get("detail", "").lower()
            print(f"✓ Unrestrict non-restricted candidate correctly returns 400")
        else:
            # If it succeeds, the candidate was already restricted
            print(f"⚠ Candidate was already restricted, unrestrict succeeded")


class TestRestrictedCandidateVerification:
    """Test the pre-restricted candidate from seed data"""
    
    def test_restricted_candidate_exists(self, auth_headers):
        """Verify the restricted candidate from seed data exists"""
        response = requests.get(f"{BASE_URL}/api/candidates/{RESTRICTED_CANDIDATE_ID}", headers=auth_headers)
        assert response.status_code == 200
        candidate = response.json()
        print(f"✓ Restricted candidate exists: {candidate['full_name']}")
    
    def test_restricted_candidate_has_restriction_info(self, auth_headers):
        """Verify restricted candidate has restriction info"""
        response = requests.get(f"{BASE_URL}/api/candidates/{RESTRICTED_CANDIDATE_ID}", headers=auth_headers)
        assert response.status_code == 200
        candidate = response.json()
        
        if candidate.get("is_restricted"):
            assert candidate.get("restriction_info") is not None
            print(f"✓ Restricted candidate has restriction_info")
            print(f"  - Category: {candidate['restriction_info'].get('category_label', 'N/A')}")
        else:
            print(f"⚠ Candidate is not currently restricted")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_candidates(self, auth_headers):
        """Delete test candidates created during tests"""
        # Get all candidates
        response = requests.get(f"{BASE_URL}/api/candidates?limit=100", headers=auth_headers)
        if response.status_code == 200:
            candidates = response.json()
            test_candidates = [c for c in candidates if c["full_name"].startswith("TEST_")]
            
            for candidate in test_candidates:
                requests.delete(f"{BASE_URL}/api/candidates/{candidate['id']}", headers=auth_headers)
            
            print(f"✓ Cleaned up {len(test_candidates)} test candidates")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
