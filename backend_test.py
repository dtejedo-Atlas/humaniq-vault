import requests
import sys
import json
from datetime import datetime

class AtlasTalentVaultTester:
    def __init__(self, base_url="https://atlas-recruiting-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {name}")
        if details:
            print(f"   Details: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if not success:
                details += f" (Expected {expected_status})"
                try:
                    error_data = response.json()
                    details += f" - {error_data.get('detail', 'Unknown error')}"
                except:
                    details += f" - {response.text[:200]}"
            
            self.log_test(name, success, details)
            
            if success:
                try:
                    return response.json()
                except:
                    return {}
            return None

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return None

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API Endpoint", "GET", "api/", 200)

    def test_user_registration(self):
        """Test user registration"""
        test_user_data = {
            "email": f"test_user_{datetime.now().strftime('%H%M%S')}@atlas.com",
            "password": "TestPass123!",
            "name": "Test User Atlas",
            "role": "recruiter"
        }
        
        result = self.run_test("User Registration", "POST", "api/auth/register", 200, test_user_data)
        if result:
            self.test_user_email = test_user_data["email"]
            self.test_user_password = test_user_data["password"]
            return True
        return False

    def test_user_login(self):
        """Test user login"""
        # Try with provided test credentials first
        login_data = {
            "email": "admin@atlas.com",
            "password": "password123"
        }
        
        result = self.run_test("User Login (Test User)", "POST", "api/auth/login", 200, login_data)
        
        if result and 'access_token' in result:
            self.token = result['access_token']
            return True
        
        # If test user doesn't exist, try with registered user
        if hasattr(self, 'test_user_email'):
            login_data = {
                "email": self.test_user_email,
                "password": self.test_user_password
            }
            result = self.run_test("User Login (Registered User)", "POST", "api/auth/login", 200, login_data)
            if result and 'access_token' in result:
                self.token = result['access_token']
                return True
        
        return False

    def test_get_current_user(self):
        """Test get current user endpoint"""
        return self.run_test("Get Current User", "GET", "api/auth/me", 200) is not None

    def test_seed_initial_data(self):
        """Test seeding initial taxonomy data"""
        return self.run_test("Seed Initial Data", "POST", "api/seed/initial-data", 200) is not None

    def test_get_industries(self):
        """Test get industries endpoint"""
        result = self.run_test("Get Industries", "GET", "api/taxonomy/industries", 200)
        if result and isinstance(result, list):
            self.log_test("Industries Data Validation", len(result) > 0, f"Found {len(result)} industries")
            return True
        return False

    def test_get_functional_areas(self):
        """Test get functional areas endpoint"""
        result = self.run_test("Get Functional Areas", "GET", "api/taxonomy/functional-areas", 200)
        if result and isinstance(result, list):
            self.log_test("Functional Areas Data Validation", len(result) > 0, f"Found {len(result)} functional areas")
            return True
        return False

    def test_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        result = self.run_test("Dashboard Stats", "GET", "api/dashboard/stats", 200)
        if result:
            required_fields = ['total_candidates', 'new_this_month', 'by_status', 'by_industry', 'by_functional_area', 'by_seniority']
            has_all_fields = all(field in result for field in required_fields)
            self.log_test("Dashboard Stats Structure", has_all_fields, f"Has required fields: {has_all_fields}")
            return has_all_fields
        return False

    def test_get_candidates(self):
        """Test get candidates endpoint"""
        result = self.run_test("Get Candidates", "GET", "api/candidates", 200)
        if result and isinstance(result, list):
            self.log_test("Candidates Data Validation", True, f"Found {len(result)} candidates")
            return True
        return False

    def test_create_candidate(self):
        """Test create candidate endpoint"""
        candidate_data = {
            "full_name": "Test Candidate Atlas",
            "email": "test.candidate@example.com",
            "phone": "+52 55 1234 5678",
            "city": "Ciudad de México",
            "state": "CDMX",
            "country": "México",
            "source": "API Test"
        }
        
        result = self.run_test("Create Candidate", "POST", "api/candidates", 200, candidate_data)
        if result and 'id' in result:
            self.test_candidate_id = result['id']
            return True
        return False

    def test_get_candidate_by_id(self):
        """Test get candidate by ID endpoint"""
        if not hasattr(self, 'test_candidate_id'):
            self.log_test("Get Candidate by ID", False, "No test candidate ID available")
            return False
        
        return self.run_test("Get Candidate by ID", "GET", f"api/candidates/{self.test_candidate_id}", 200) is not None

    def test_update_candidate(self):
        """Test update candidate endpoint"""
        if not hasattr(self, 'test_candidate_id'):
            self.log_test("Update Candidate", False, "No test candidate ID available")
            return False
        
        update_data = {
            "current_company": "Test Company Updated",
            "current_title": "Senior Test Engineer",
            "status": "reviewed"
        }
        
        return self.run_test("Update Candidate", "PUT", f"api/candidates/{self.test_candidate_id}", 200, update_data) is not None

    def test_recent_activity(self):
        """Test recent activity endpoint"""
        result = self.run_test("Recent Activity", "GET", "api/dashboard/recent-activity", 200)
        if result and isinstance(result, list):
            self.log_test("Recent Activity Data", True, f"Found {len(result)} activity logs")
            return True
        return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Atlas Talent Vault API Tests")
        print("=" * 50)
        
        # Basic connectivity
        self.test_root_endpoint()
        
        # Authentication flow
        self.test_user_registration()
        login_success = self.test_user_login()
        
        if not login_success:
            print("\n❌ Authentication failed - stopping tests")
            return False
        
        self.test_get_current_user()
        
        # Seed data
        self.test_seed_initial_data()
        
        # Taxonomy endpoints
        self.test_get_industries()
        self.test_get_functional_areas()
        
        # Dashboard endpoints
        self.test_dashboard_stats()
        self.test_recent_activity()
        
        # Candidate management
        self.test_get_candidates()
        self.test_create_candidate()
        self.test_get_candidate_by_id()
        self.test_update_candidate()
        
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.tests_passed < self.tests_run:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = AtlasTalentVaultTester()
    
    try:
        success = tester.run_all_tests()
        tester.print_summary()
        
        # Save detailed results
        with open('/app/backend_test_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': tester.tests_run,
                    'passed_tests': tester.tests_passed,
                    'failed_tests': tester.tests_run - tester.tests_passed,
                    'success_rate': tester.tests_passed / tester.tests_run * 100 if tester.tests_run > 0 else 0
                },
                'detailed_results': tester.test_results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())