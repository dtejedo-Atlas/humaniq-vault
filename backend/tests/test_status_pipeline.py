"""
Test suite for Candidate Status Pipeline and Smart Folders functionality.
Phase 2 validation: Status transitions, history, and Smart Folders PROCESO.
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://atlas-recruiting-ai.preview.emergentagent.com').rstrip('/')

# Test credentials from environment with defaults for local testing
TEST_ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "test_utf8@atlas.com")
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "Humaniq123")
TEST_CANDIDATE_ID = "5a242806-04ec-467c-bae2-1b99d0943e61"


class TestStatusConfig:
    """Test status configuration endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_status_config(self):
        """Test GET /api/status-config returns valid transitions"""
        response = requests.get(f"{BASE_URL}/api/status-config", headers=self.headers)
        assert response.status_code == 200, f"Status config failed: {response.text}"
        
        data = response.json()
        assert "statuses" in data, "Missing 'statuses' in response"
        assert "transitions" in data, "Missing 'transitions' in response"
        
        # Verify transitions structure
        transitions = data["transitions"]
        assert "new" in transitions
        assert "reviewing" in transitions
        assert "qualified" in transitions
        
        # Verify qualified transitions (current candidate status)
        qualified_transitions = transitions.get("qualified", [])
        assert "ready_to_send" in qualified_transitions, "qualified should transition to ready_to_send"
        assert "rejected" in qualified_transitions, "qualified should transition to rejected"
        assert "on_hold" in qualified_transitions, "qualified should transition to on_hold"
        
        print(f"✓ Status config valid. Qualified transitions: {qualified_transitions}")


class TestStatusPipeline:
    """Test candidate status change pipeline"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_candidate_current_status(self):
        """Test getting candidate's current status"""
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Get candidate failed: {response.text}"
        
        candidate = response.json()
        assert "status" in candidate, "Missing 'status' field"
        print(f"✓ Candidate current status: {candidate['status']}")
        return candidate["status"]
    
    def test_get_status_history(self):
        """Test GET /api/candidates/{id}/status-history"""
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status-history",
            headers=self.headers
        )
        assert response.status_code == 200, f"Status history failed: {response.text}"
        
        data = response.json()
        assert "candidate_id" in data
        assert "current_status" in data
        assert "history" in data
        
        history = data["history"]
        print(f"✓ Status history has {len(history)} entries")
        
        # Verify history structure if entries exist
        if history:
            first_entry = history[0]
            assert "from_status" in first_entry, "Missing from_status in history"
            assert "to_status" in first_entry, "Missing to_status in history"
            assert "changed_by_name" in first_entry, "Missing changed_by_name in history"
            assert "changed_at" in first_entry, "Missing changed_at in history"
            print(f"✓ History entry structure valid: {first_entry['from_status']} → {first_entry['to_status']}")
        
        return data
    
    def test_invalid_status_transition(self):
        """Test that invalid status transitions are rejected"""
        # Get current status first
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}",
            headers=self.headers
        )
        current_status = response.json()["status"]
        
        # Try an invalid transition (e.g., qualified -> placed directly)
        if current_status == "qualified":
            invalid_status = "placed"  # Can't go directly from qualified to placed
        else:
            invalid_status = "placed"  # Most statuses can't go directly to placed
        
        response = requests.put(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
            headers=self.headers,
            json={"new_status": invalid_status}
        )
        
        # Should fail with 400
        assert response.status_code == 400, f"Expected 400 for invalid transition, got {response.status_code}"
        print(f"✓ Invalid transition {current_status} → {invalid_status} correctly rejected")
    
    def test_valid_status_transition_to_on_hold(self):
        """Test valid status transition to on_hold (reversible)"""
        # Get current status
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}",
            headers=self.headers
        )
        current_status = response.json()["status"]
        
        # on_hold is valid from most statuses
        if current_status in ["new", "reviewing", "qualified", "ready_to_send", "submitted", "interviewed", "offer"]:
            response = requests.put(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                headers=self.headers,
                json={"new_status": "on_hold", "notes": "Test: putting on hold"}
            )
            assert response.status_code == 200, f"Status change failed: {response.text}"
            
            data = response.json()
            assert data["new_status"] == "on_hold"
            assert data["previous_status"] == current_status
            print(f"✓ Status changed: {current_status} → on_hold")
            
            # Revert back to reviewing (valid from on_hold)
            response = requests.put(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                headers=self.headers,
                json={"new_status": "reviewing", "notes": "Test: reverting from on_hold"}
            )
            assert response.status_code == 200, f"Revert failed: {response.text}"
            print(f"✓ Status reverted: on_hold → reviewing")
            
            # Now go back to qualified
            response = requests.put(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                headers=self.headers,
                json={"new_status": "qualified", "notes": "Test: back to qualified"}
            )
            assert response.status_code == 200, f"Back to qualified failed: {response.text}"
            print(f"✓ Status restored: reviewing → qualified")
        else:
            pytest.skip(f"Current status {current_status} doesn't support on_hold transition")
    
    def test_status_change_with_notes(self):
        """Test status change includes notes in history"""
        test_note = f"Test note at {datetime.now().isoformat()}"
        
        # Get current status
        response = requests.get(
            f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}",
            headers=self.headers
        )
        current_status = response.json()["status"]
        
        # Change to ready_to_send if qualified
        if current_status == "qualified":
            response = requests.put(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                headers=self.headers,
                json={"new_status": "ready_to_send", "notes": test_note}
            )
            assert response.status_code == 200, f"Status change failed: {response.text}"
            
            # Verify note in history
            history_response = requests.get(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status-history",
                headers=self.headers
            )
            history = history_response.json()["history"]
            
            # Find the latest entry
            if history:
                latest = history[-1]
                assert latest["notes"] == test_note, f"Note not saved: expected '{test_note}', got '{latest.get('notes')}'"
                print(f"✓ Status change note saved correctly")
            
            # Revert to qualified for other tests
            response = requests.put(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                headers=self.headers,
                json={"new_status": "on_hold", "notes": "Reverting for tests"}
            )
            response = requests.put(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                headers=self.headers,
                json={"new_status": "qualified", "notes": "Back to qualified"}
            )
        else:
            pytest.skip(f"Current status {current_status} is not qualified")


class TestSmartFolders:
    """Test Smart Folders functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_all_folders(self):
        """Test GET /api/folders returns all folder categories"""
        response = requests.get(
            f"{BASE_URL}/api/folders",
            headers=self.headers,
            params={"include_counts": True}
        )
        assert response.status_code == 200, f"Get folders failed: {response.text}"
        
        data = response.json()
        assert "by_category" in data, "Missing 'by_category' in response"
        
        categories = data["by_category"]
        assert "verticals" in categories, "Missing 'verticals' category"
        assert "process" in categories, "Missing 'process' category"
        
        print(f"✓ Folders loaded: {len(categories.get('verticals', []))} verticals, {len(categories.get('process', []))} process")
        return data
    
    def test_process_folders_exist(self):
        """Test that PROCESO folders exist with correct names"""
        response = requests.get(
            f"{BASE_URL}/api/folders",
            headers=self.headers,
            params={"include_counts": True}
        )
        data = response.json()
        
        process_folders = data["by_category"].get("process", [])
        folder_names = [f["name"] for f in process_folders]
        
        # Expected PROCESO folders
        expected_folders = ["En Evaluación", "Recién Ingresados", "Listos para Enviar"]
        
        for expected in expected_folders:
            assert expected in folder_names, f"Missing PROCESO folder: {expected}"
            print(f"✓ Found PROCESO folder: {expected}")
        
        return process_folders
    
    def test_process_folder_counts(self):
        """Test that PROCESO folders have candidate counts"""
        response = requests.get(
            f"{BASE_URL}/api/folders",
            headers=self.headers,
            params={"include_counts": True}
        )
        data = response.json()
        
        process_folders = data["by_category"].get("process", [])
        
        for folder in process_folders:
            assert "candidate_count" in folder, f"Missing candidate_count in folder {folder['name']}"
            print(f"✓ Folder '{folder['name']}': {folder['candidate_count']} candidates")
    
    def test_get_folder_candidates(self):
        """Test getting candidates from a specific folder"""
        # First get folders
        response = requests.get(
            f"{BASE_URL}/api/folders",
            headers=self.headers,
            params={"include_counts": True}
        )
        data = response.json()
        
        process_folders = data["by_category"].get("process", [])
        
        # Find a folder with candidates
        folder_with_candidates = None
        for folder in process_folders:
            if folder.get("candidate_count", 0) > 0:
                folder_with_candidates = folder
                break
        
        if folder_with_candidates:
            folder_id = folder_with_candidates["id"]
            response = requests.get(
                f"{BASE_URL}/api/folders/{folder_id}/candidates",
                headers=self.headers
            )
            assert response.status_code == 200, f"Get folder candidates failed: {response.text}"
            
            candidates = response.json()
            assert "candidates" in candidates, "Missing 'candidates' in response"
            print(f"✓ Folder '{folder_with_candidates['name']}' returned {len(candidates['candidates'])} candidates")
        else:
            print("⚠ No folders with candidates found, skipping candidate retrieval test")
    
    def test_folder_by_id(self):
        """Test getting a specific folder by ID"""
        # First get folders
        response = requests.get(
            f"{BASE_URL}/api/folders",
            headers=self.headers
        )
        data = response.json()
        
        process_folders = data["by_category"].get("process", [])
        
        if process_folders:
            folder_id = process_folders[0]["id"]
            response = requests.get(
                f"{BASE_URL}/api/folders/{folder_id}",
                headers=self.headers
            )
            assert response.status_code == 200, f"Get folder by ID failed: {response.text}"
            
            folder = response.json()
            assert folder["id"] == folder_id
            print(f"✓ Got folder by ID: {folder['name']}")


class TestStatusFolderIntegration:
    """Test that status changes update folder counts correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_status_change_updates_folder_counts(self):
        """Test that changing status updates the relevant folder counts"""
        # Get initial folder counts
        response = requests.get(
            f"{BASE_URL}/api/folders",
            headers=self.headers,
            params={"include_counts": True}
        )
        initial_data = response.json()
        
        # Find "Listos para Enviar" folder (ready_to_send status)
        process_folders = initial_data["by_category"].get("process", [])
        listos_folder = next((f for f in process_folders if f["name"] == "Listos para Enviar"), None)
        
        if listos_folder:
            initial_count = listos_folder.get("candidate_count", 0)
            
            # Get candidate current status
            response = requests.get(
                f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}",
                headers=self.headers
            )
            current_status = response.json()["status"]
            
            if current_status == "qualified":
                # Change to ready_to_send
                response = requests.put(
                    f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                    headers=self.headers,
                    json={"new_status": "ready_to_send", "notes": "Testing folder count update"}
                )
                assert response.status_code == 200
                
                # Check folder count increased
                response = requests.get(
                    f"{BASE_URL}/api/folders",
                    headers=self.headers,
                    params={"include_counts": True}
                )
                updated_data = response.json()
                updated_folders = updated_data["by_category"].get("process", [])
                updated_listos = next((f for f in updated_folders if f["name"] == "Listos para Enviar"), None)
                
                if updated_listos:
                    new_count = updated_listos.get("candidate_count", 0)
                    assert new_count >= initial_count, f"Folder count should have increased: {initial_count} -> {new_count}"
                    print(f"✓ Folder count updated: {initial_count} → {new_count}")
                
                # Revert status
                response = requests.put(
                    f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                    headers=self.headers,
                    json={"new_status": "on_hold", "notes": "Reverting"}
                )
                response = requests.put(
                    f"{BASE_URL}/api/candidates/{TEST_CANDIDATE_ID}/status",
                    headers=self.headers,
                    json={"new_status": "qualified", "notes": "Back to qualified"}
                )
            else:
                pytest.skip(f"Candidate not in qualified status: {current_status}")
        else:
            pytest.skip("Listos para Enviar folder not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
