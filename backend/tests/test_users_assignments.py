"""
Test Suite for Multi-user Roles and Candidate Assignments
=========================================================
Tests for:
- User management endpoints (Admin only)
- Candidate assignment endpoints
- Permission checks (Admin vs Recruiter)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://atlas-recruiting-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASSWORD = "test123456"
RECRUITER_EMAIL = "recruiter_test@atlas.com"
RECRUITER_PASSWORD = "test123456"
TEST_CANDIDATE_ID = "e75df560-272d-44ba-b902-e859a0638a7b"


class TestUserManagement:
    """Tests for User Management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup tokens for each test"""
        # Get admin token
        admin_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert admin_response.status_code == 200, f"Admin login failed: {admin_response.text}"
        self.admin_token = admin_response.json()["access_token"]
        self.admin_user = admin_response.json()["user"]
        
        # Get recruiter token
        recruiter_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
        )
        assert recruiter_response.status_code == 200, f"Recruiter login failed: {recruiter_response.text}"
        self.recruiter_token = recruiter_response.json()["access_token"]
        self.recruiter_user = recruiter_response.json()["user"]
    
    # ========== GET /api/users Tests ==========
    
    def test_admin_can_list_users(self):
        """GET /api/users - Admin can list all users"""
        response = requests.get(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "users" in data, "Response should contain 'users' key"
        assert "total" in data, "Response should contain 'total' key"
        assert isinstance(data["users"], list), "Users should be a list"
        assert len(data["users"]) > 0, "Should have at least one user"
        
        # Verify no password_hash exposed
        for user in data["users"]:
            assert "password_hash" not in user, "password_hash should not be exposed"
            assert "hashed_password" not in user, "hashed_password should not be exposed"
            assert "id" in user, "User should have id"
            assert "email" in user, "User should have email"
            assert "role" in user, "User should have role"
        
        print(f"✓ Admin listed {len(data['users'])} users successfully")
    
    def test_recruiter_cannot_list_users(self):
        """GET /api/users - Recruiter gets 403 Forbidden"""
        response = requests.get(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Recruiter correctly denied access to user list")
    
    # ========== POST /api/users Tests ==========
    
    def test_admin_can_create_user(self):
        """POST /api/users - Admin can create new user"""
        import uuid
        test_email = f"test_user_{uuid.uuid4().hex[:8]}@atlas.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={
                "email": test_email,
                "password": "testpassword123",
                "name": "Test User Created",
                "role": "recruiter"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify created user data
        assert data["email"] == test_email.lower(), "Email should match"
        assert data["name"] == "Test User Created", "Name should match"
        assert data["role"] == "recruiter", "Role should match"
        assert "id" in data, "Should have id"
        assert "password_hash" not in data, "password_hash should not be returned"
        
        print(f"✓ Admin created user {test_email} successfully")
    
    def test_recruiter_cannot_create_user(self):
        """POST /api/users - Recruiter cannot create users"""
        import uuid
        test_email = f"test_user_{uuid.uuid4().hex[:8]}@atlas.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {self.recruiter_token}"},
            json={
                "email": test_email,
                "password": "testpassword123",
                "name": "Test User",
                "role": "recruiter"
            }
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Recruiter correctly denied user creation")
    
    # ========== GET /api/users/me Tests ==========
    
    def test_get_current_user_with_permissions(self):
        """GET /api/users/me - Returns user with can_manage_users and can_assign_candidates flags"""
        # Test admin
        admin_response = requests.get(
            f"{BASE_URL}/api/users/me",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert admin_response.status_code == 200, f"Expected 200, got {admin_response.status_code}"
        admin_data = admin_response.json()
        
        assert "can_manage_users" in admin_data, "Should have can_manage_users flag"
        assert "can_assign_candidates" in admin_data, "Should have can_assign_candidates flag"
        assert admin_data["can_manage_users"] == True, "Admin should be able to manage users"
        assert admin_data["can_assign_candidates"] == True, "Admin should be able to assign candidates"
        
        # Test recruiter
        recruiter_response = requests.get(
            f"{BASE_URL}/api/users/me",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        
        assert recruiter_response.status_code == 200
        recruiter_data = recruiter_response.json()
        
        assert "can_manage_users" in recruiter_data, "Should have can_manage_users flag"
        assert "can_assign_candidates" in recruiter_data, "Should have can_assign_candidates flag"
        assert recruiter_data["can_manage_users"] == False, "Recruiter should not manage users"
        assert recruiter_data["can_assign_candidates"] == False, "Recruiter should not assign candidates"
        
        print("✓ /users/me returns correct permission flags for admin and recruiter")
    
    # ========== GET /api/users/recruiters Tests ==========
    
    def test_admin_can_get_recruiters_list(self):
        """GET /api/users/recruiters - Admin can get list of recruiters"""
        response = requests.get(
            f"{BASE_URL}/api/users/recruiters",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "recruiters" in data, "Response should contain 'recruiters' key"
        assert isinstance(data["recruiters"], list), "Recruiters should be a list"
        
        # Verify recruiter data structure
        for recruiter in data["recruiters"]:
            assert "id" in recruiter, "Recruiter should have id"
            assert "name" in recruiter, "Recruiter should have name"
            assert "role" in recruiter, "Recruiter should have role"
            assert "password_hash" not in recruiter, "password_hash should not be exposed"
        
        print(f"✓ Admin retrieved {len(data['recruiters'])} recruiters")
    
    def test_recruiter_cannot_get_recruiters_list(self):
        """GET /api/users/recruiters - Recruiter gets 403"""
        response = requests.get(
            f"{BASE_URL}/api/users/recruiters",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Recruiter correctly denied access to recruiters list")


class TestCandidateAssignments:
    """Tests for Candidate Assignment endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup tokens for each test"""
        # Get admin token
        admin_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert admin_response.status_code == 200
        self.admin_token = admin_response.json()["access_token"]
        self.admin_user = admin_response.json()["user"]
        
        # Get recruiter token
        recruiter_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
        )
        assert recruiter_response.status_code == 200
        self.recruiter_token = recruiter_response.json()["access_token"]
        self.recruiter_user = recruiter_response.json()["user"]
    
    # ========== POST /api/candidates/{id}/assign Tests ==========
    
    def test_admin_can_assign_candidate(self):
        """POST /api/candidates/{id}/assign - Admin can assign candidate to recruiter"""
        # First get a candidate to assign
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=1",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        candidate_id = candidates[0]["id"]
        
        # Assign to recruiter
        response = requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/assign",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={
                "candidate_id": candidate_id,
                "recruiter_id": self.recruiter_user["id"],
                "notes": "Test assignment"
            }
        )
        
        # Could be 200 (success) or 400 (already assigned)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data, "Assignment should have id"
            assert data["candidate_id"] == candidate_id, "Candidate ID should match"
            assert data["recruiter_id"] == self.recruiter_user["id"], "Recruiter ID should match"
            print(f"✓ Admin assigned candidate {candidate_id} to recruiter")
        else:
            print(f"✓ Candidate already assigned (expected behavior)")
    
    def test_recruiter_cannot_assign_candidate(self):
        """POST /api/candidates/{id}/assign - Recruiter cannot assign candidates"""
        # Get a candidate
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=1",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        candidate_id = candidates[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/assign",
            headers={"Authorization": f"Bearer {self.recruiter_token}"},
            json={
                "candidate_id": candidate_id,
                "recruiter_id": self.recruiter_user["id"],
                "notes": "Test"
            }
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Recruiter correctly denied assignment permission")
    
    # ========== GET /api/candidates/{id}/can-edit Tests ==========
    
    def test_admin_can_edit_any_candidate(self):
        """GET /api/candidates/{id}/can-edit - Admin returns can_edit: true"""
        # Get a candidate
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=1",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        candidate_id = candidates[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/candidates/{candidate_id}/can-edit",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "can_edit" in data, "Response should have can_edit field"
        assert data["can_edit"] == True, "Admin should be able to edit any candidate"
        assert "user_role" in data, "Response should have user_role"
        assert data["user_role"] == "admin", "User role should be admin"
        
        print(f"✓ Admin can edit candidate {candidate_id}")
    
    def test_recruiter_cannot_edit_unassigned_candidate(self):
        """GET /api/candidates/{id}/can-edit - Recruiter (not assigned) returns can_edit: false with reason"""
        # Get a candidate that is NOT assigned to this recruiter
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=10",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        # Find a candidate not assigned to this recruiter
        unassigned_candidate_id = None
        for candidate in candidates:
            # Check if assigned to this recruiter
            assignments_response = requests.get(
                f"{BASE_URL}/api/candidates/{candidate['id']}/assignments",
                headers={"Authorization": f"Bearer {self.recruiter_token}"}
            )
            if assignments_response.status_code == 200:
                assignments = assignments_response.json().get("assignments", [])
                is_assigned = any(a["recruiter_id"] == self.recruiter_user["id"] for a in assignments)
                if not is_assigned:
                    unassigned_candidate_id = candidate["id"]
                    break
        
        if not unassigned_candidate_id:
            pytest.skip("All candidates are assigned to this recruiter")
        
        response = requests.get(
            f"{BASE_URL}/api/candidates/{unassigned_candidate_id}/can-edit",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "can_edit" in data, "Response should have can_edit field"
        assert data["can_edit"] == False, "Recruiter should not be able to edit unassigned candidate"
        assert "reason" in data, "Response should have reason when can_edit is false"
        assert data["reason"] is not None, "Reason should not be None"
        assert "user_role" in data, "Response should have user_role"
        assert data["user_role"] == "recruiter", "User role should be recruiter"
        
        print(f"✓ Recruiter cannot edit unassigned candidate. Reason: {data['reason']}")
    
    # ========== GET /api/candidates/{id}/assignments Tests ==========
    
    def test_get_candidate_assignments(self):
        """GET /api/candidates/{id}/assignments - Returns list of assignments"""
        # Get a candidate
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=1",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        candidate_id = candidates[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/candidates/{candidate_id}/assignments",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "assignments" in data, "Response should have assignments field"
        assert isinstance(data["assignments"], list), "Assignments should be a list"
        
        # If there are assignments, verify structure
        for assignment in data["assignments"]:
            assert "id" in assignment, "Assignment should have id"
            assert "candidate_id" in assignment, "Assignment should have candidate_id"
            assert "recruiter_id" in assignment, "Assignment should have recruiter_id"
            assert "recruiter_name" in assignment, "Assignment should have recruiter_name"
        
        print(f"✓ Retrieved {len(data['assignments'])} assignments for candidate {candidate_id}")
    
    # ========== GET /api/assignments/my Tests ==========
    
    def test_recruiter_get_my_assignments(self):
        """GET /api/assignments/my - Recruiter gets their assigned candidates"""
        response = requests.get(
            f"{BASE_URL}/api/assignments/my",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "assignments" in data, "Response should have assignments field"
        assert "total" in data, "Response should have total field"
        assert isinstance(data["assignments"], list), "Assignments should be a list"
        
        # Verify all assignments belong to this recruiter
        for assignment in data["assignments"]:
            assert assignment["recruiter_id"] == self.recruiter_user["id"], "All assignments should be for this recruiter"
        
        print(f"✓ Recruiter has {data['total']} assigned candidates")
    
    # ========== DELETE /api/candidates/{id}/assign/{recruiter_id} Tests ==========
    
    def test_admin_can_unassign_candidate(self):
        """DELETE /api/candidates/{id}/assign/{recruiter_id} - Admin can unassign"""
        # First, ensure there's an assignment to delete
        # Get a candidate and assign it
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=1",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        candidate_id = candidates[0]["id"]
        
        # Try to assign first (might already be assigned)
        assign_response = requests.post(
            f"{BASE_URL}/api/candidates/{candidate_id}/assign",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={
                "candidate_id": candidate_id,
                "recruiter_id": self.recruiter_user["id"],
                "notes": "Test for unassign"
            }
        )
        
        # Now try to unassign
        response = requests.delete(
            f"{BASE_URL}/api/candidates/{candidate_id}/assign/{self.recruiter_user['id']}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        # Could be 200 (success) or 400 (not found)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data, "Response should have message"
            print(f"✓ Admin unassigned candidate {candidate_id}")
        else:
            print(f"✓ No assignment found to delete (expected if not assigned)")
    
    def test_recruiter_cannot_unassign_candidate(self):
        """DELETE /api/candidates/{id}/assign/{recruiter_id} - Recruiter cannot unassign"""
        # Get a candidate
        candidates_response = requests.get(
            f"{BASE_URL}/api/candidates?limit=1",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()
        
        if len(candidates) == 0:
            pytest.skip("No candidates available for testing")
        
        candidate_id = candidates[0]["id"]
        
        response = requests.delete(
            f"{BASE_URL}/api/candidates/{candidate_id}/assign/{self.recruiter_user['id']}",
            headers={"Authorization": f"Bearer {self.recruiter_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Recruiter correctly denied unassignment permission")


class TestSpecificCandidate:
    """Tests using the specific test candidate ID"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup tokens for each test"""
        # Get admin token
        admin_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert admin_response.status_code == 200
        self.admin_token = admin_response.json()["access_token"]
        self.admin_user = admin_response.json()["user"]
        
        # Get recruiter token
        recruiter_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
        )
        assert recruiter_response.status_code == 200
        self.recruiter_token = recruiter_response.json()["access_token"]
        self.recruiter_user = recruiter_response.json()["user"]
    
    def test_specific_candidate_exists(self):
        """Verify test candidate exists"""
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        # Candidate might not exist
        if response.status_code == 404:
            pytest.skip(f"Test candidate {TEST_CANDIDATE_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["id"] == TEST_CANDIDATE_ID
        print(f"✓ Test candidate exists: {data.get('full_name', 'Unknown')}")
    
    def test_specific_candidate_assignments(self):
        """Test assignments for specific candidate"""
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/assignments",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip(f"Test candidate {TEST_CANDIDATE_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"✓ Test candidate has {len(data.get('assignments', []))} assignments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
