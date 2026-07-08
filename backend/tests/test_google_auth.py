"""Tests for Google OAuth (Emergent-managed) integration and JWT login regression."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASSWORD = "Humaniq123"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============= Google OAuth Endpoint Tests =============

class TestGoogleSessionEndpoint:
    def test_missing_body_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/auth/google/session")
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_missing_session_id_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/auth/google/session", json={})
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_empty_session_id_returns_422_or_401(self, api):
        r = api.post(f"{BASE_URL}/api/auth/google/session", json={"session_id": ""})
        # Empty string may pass Pydantic (str type) but fail upstream (401)
        assert r.status_code in (422, 401), f"Expected 422/401, got {r.status_code}: {r.text}"

    def test_invalid_session_id_returns_401(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/google/session",
            json={"session_id": "totally_fake_invalid_session_12345"}
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        data = r.json()
        assert "detail" in data
        assert "Google" in data["detail"] or "inv" in data["detail"].lower()

    def test_wrong_field_name_returns_422(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/google/session",
            json={"sessionId": "camelCase_wrong_field"}
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ============= JWT Login Regression Tests =============

class TestJwtLoginRegression:
    def test_admin_login_success(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20
        assert "user" in data
        assert data["user"]["email"].lower() == ADMIN_EMAIL.lower()

    def test_get_me_with_jwt(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert r.status_code == 200
        token = r.json()["access_token"]

        r2 = api.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r2.status_code == 200, f"/auth/me failed: {r2.status_code} {r2.text}"
        me = r2.json()
        assert me["email"].lower() == ADMIN_EMAIL.lower()
        assert "role" in me

    def test_wrong_password_401(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrongpass_xyz"}
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
