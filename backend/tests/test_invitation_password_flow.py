"""End-to-end tests for the invitation + set-password + change-password flow.

Covers:
- POST /api/users (create invited user, no password_hash, email failure propagated)
- GET /api/users (invitation_pending flag; no password_hash exposed)
- POST /api/auth/validate-setup-token / set-password (E2E with real token via invitation_service)
- Token reuse rejection
- Login with new password
- Invalid tokens
- Password length validation
- Login of invited user with no password
- POST /api/users/{id}/resend-invitation
- POST /api/users/{id}/send-password-reset
- POST /api/auth/change-password
- Recruiter permission checks (403)
- activity_logs entries for user_invited / password_set / password_changed
- Regression: normal admin login works; google session invalid still 401
"""
import os
import sys
import time
import uuid
import asyncio
import hashlib
import pytest
import requests

# Add backend to path for direct service calls
BACKEND_DIR = "/app/backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASSWORD = "Humaniq123"
RECRUITER_EMAIL = "dtejedo@gmail.com"
RECRUITER_PASSWORD = "Humaniq2026!"

# Emails will fail Resend (test mode only accepts diego@humaniq.com.mx) — this is EXPECTED
FAKE_INVITEE_1 = f"test_invite_{uuid.uuid4().hex[:8]}@testing-fake-domain.com"
FAKE_INVITEE_2 = f"test_invite_{uuid.uuid4().hex[:8]}@testing-fake-domain.com"
FAKE_INVITEE_3 = f"test_invite_{uuid.uuid4().hex[:8]}@testing-fake-domain.com"

# Shared state across tests
STATE = {}


def _db():
    """Return the same DB client the backend uses (ATLAS_URI has priority)."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    url = os.environ.get("ATLAS_URI") or os.environ.get("MONGO_URL")
    if os.environ.get("ATLAS_URI") and os.environ.get("ATLAS_DB_NAME"):
        db_name = os.environ["ATLAS_DB_NAME"]
    else:
        db_name = os.environ["DB_NAME"]
    return AsyncIOMotorClient(url)[db_name]


def _run(coro):
    """Run an async coroutine synchronously inside pytest."""
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def recruiter_token():
    r = requests.post(f"{API}/auth/login", json={"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"recruiter login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def recruiter_headers(recruiter_token):
    return {"Authorization": f"Bearer {recruiter_token}", "Content-Type": "application/json"}


# -------- Cleanup at module teardown --------
@pytest.fixture(scope="module", autouse=True)
def cleanup_created_users():
    yield
    async def _clean():
        db = _db()
        emails = [FAKE_INVITEE_1, FAKE_INVITEE_2, FAKE_INVITEE_3]
        users = await db.users.find({"email": {"$in": [e.lower() for e in emails]}}, {"id": 1, "_id": 0}).to_list(50)
        user_ids = [u["id"] for u in users]
        if user_ids:
            await db.password_tokens.delete_many({"user_id": {"$in": user_ids}})
        await db.users.delete_many({"email": {"$in": [e.lower() for e in emails]}})
    try:
        asyncio.run(_clean())
    except Exception as e:
        print(f"cleanup warning: {e}")


# =========================================================
# 1. Create invited user — no password_hash, email_sent=false with clear error
# =========================================================
def test_01_create_invited_user_email_fails_but_user_created(admin_headers):
    payload = {
        "email": FAKE_INVITEE_1,
        "name": "Invitee One",
        "role": "recruiter",
        "origin": BASE_URL,
    }
    r = requests.post(f"{API}/users", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code == 200, f"create user failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["email"] == FAKE_INVITEE_1.lower()
    assert data["invitation_pending"] is True
    assert data["email_sent"] is False, f"Expected email_sent=False for fake email, got {data}"
    assert data.get("email_error"), "Expected email_error to be populated when Resend rejects"
    assert "password_hash" not in data
    STATE["user1_id"] = data["id"]
    STATE["user1_email"] = data["email"]


# =========================================================
# 2. GET /users — invitation_pending flags & no password_hash exposure
# =========================================================
def test_02_list_users_invitation_pending_flags(admin_headers):
    r = requests.get(f"{API}/users", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    users = r.json()["users"]
    by_email = {u["email"]: u for u in users}
    assert FAKE_INVITEE_1.lower() in by_email
    invited = by_email[FAKE_INVITEE_1.lower()]
    assert invited["invitation_pending"] is True
    admin_row = by_email.get(ADMIN_EMAIL)
    assert admin_row is not None
    assert admin_row["invitation_pending"] is False
    # Never expose password_hash
    for u in users:
        assert "password_hash" not in u
        assert "hashed_password" not in u


# =========================================================
# 3. password_tokens document created with sha256 hash (not plaintext)
# =========================================================
def test_03_password_tokens_stored_hashed():
    async def _check():
        import invitation_service
        db = _db()
        # Ensure at least one token exists for user1 (from the create step above).
        # If email failed BEFORE the create_token call, there won't be one; but backend creates
        # the token BEFORE trying to send the email, so one should exist.
        docs = await db.password_tokens.find({"user_id": STATE["user1_id"]}).to_list(10)
        assert docs, "expected token doc for invited user"
        for d in docs:
            assert d.get("token_hash") and len(d["token_hash"]) == 64  # sha256 hex
            assert d.get("purpose") == "invitation"
            assert d.get("expires_at")
            # token itself is NOT stored in plaintext
            for k, v in d.items():
                if isinstance(v, str) and len(v) > 30 and v != d.get("token_hash"):
                    # some fields like id are uuids (~36); token_urlsafe(32) → 43 chars
                    # ensure no raw token-like value stored except hash
                    assert not (len(v) == 43 and not v.startswith("hash"))
    asyncio.run(_check())


# =========================================================
# 4. Full E2E: generate token → validate → set-password → reuse blocked → login OK
# =========================================================
def test_04_e2e_set_password_flow(admin_headers):
    async def _gen():
        import invitation_service
        db = _db()
        # Get the admin's user id (creator)
        admin_doc = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1, "_id": 0})
        token = await invitation_service.create_token(db, STATE["user1_id"], "invitation", admin_doc["id"])
        return token
    token = asyncio.run(_gen())
    assert token and len(token) > 30
    STATE["user1_token"] = token

    # validate-setup-token
    r = requests.post(f"{API}/auth/validate-setup-token", json={"token": token}, timeout=30)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["valid"] is True
    assert v["email"] == FAKE_INVITEE_1.lower()
    assert v["purpose"] == "invitation"

    # set-password
    new_pw = "NuevaPass123"
    r = requests.post(f"{API}/auth/set-password", json={"token": token, "password": new_pw}, timeout=30)
    assert r.status_code == 200, r.text

    # reuse blocked
    r2 = requests.post(f"{API}/auth/set-password", json={"token": token, "password": new_pw}, timeout=30)
    assert r2.status_code == 400, f"expected 400 on token reuse, got {r2.status_code} {r2.text}"

    # login works with new password
    r3 = requests.post(f"{API}/auth/login", json={"email": FAKE_INVITEE_1, "password": new_pw}, timeout=30)
    assert r3.status_code == 200, r3.text
    tk = r3.json().get("access_token")
    assert tk and len(tk) > 20
    STATE["user1_password"] = new_pw
    STATE["user1_login_token"] = tk


# =========================================================
# 5. Invalid tokens
# =========================================================
def test_05_invalid_token_validate():
    r = requests.post(f"{API}/auth/validate-setup-token", json={"token": "garbage-token-xxx"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_06_invalid_token_set_password():
    r = requests.post(f"{API}/auth/set-password", json={"token": "garbage-token-xxx", "password": "SomePass123"}, timeout=30)
    assert r.status_code == 400
    assert "detail" in r.json()


# =========================================================
# 7. Password length validation
# =========================================================
def test_07_short_password_rejected():
    # Use a fresh valid token so we're testing password length, not token validity
    async def _gen():
        import invitation_service
        db = _db()
        admin_doc = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1, "_id": 0})
        # create a fresh invitee for this test
        return admin_doc["id"]
    # simpler: just call with a bogus token AND short password. Since backend
    # validates length BEFORE token, we should still get 400 with clear msg.
    r = requests.post(f"{API}/auth/set-password", json={"token": "anything", "password": "short"}, timeout=30)
    assert r.status_code == 400
    assert "8 caracteres" in r.json()["detail"]


# =========================================================
# 8. Login of invited user without password → 401 with clear message
# =========================================================
def test_08_login_invited_user_no_password_yet(admin_headers):
    payload = {
        "email": FAKE_INVITEE_2,
        "name": "Invitee Two",
        "role": "recruiter",
        "origin": BASE_URL,
    }
    r = requests.post(f"{API}/users", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    STATE["user2_id"] = r.json()["id"]

    r2 = requests.post(f"{API}/auth/login", json={"email": FAKE_INVITEE_2, "password": "AnyPass123"}, timeout=30)
    assert r2.status_code == 401
    detail = r2.json().get("detail", "")
    assert "contraseña" in detail.lower() or "invitación" in detail.lower(), f"unexpected msg: {detail}"


# =========================================================
# 9. Resend invitation: pending → 200 {sent:false, error}; with password → 400
# =========================================================
def test_09_resend_invitation_pending_user_returns_sent_false(admin_headers):
    r = requests.post(
        f"{API}/users/{STATE['user2_id']}/resend-invitation",
        headers=admin_headers,
        json={"origin": BASE_URL},
        timeout=30,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text[:200]}"
    body = r.json()
    assert body["sent"] is False
    assert "testing emails" in body["error"] or len(body["error"]) > 0


def test_10_resend_invitation_user_with_password_returns_400(admin_headers):
    r = requests.post(
        f"{API}/users/{STATE['user1_id']}/resend-invitation",
        headers=admin_headers,
        json={"origin": BASE_URL},
        timeout=30,
    )
    assert r.status_code == 400
    assert "ya estableció" in r.json()["detail"] or "Restablecer" in r.json()["detail"]


# =========================================================
# 10. send-password-reset: user with password → 200 {sent:false} (fake email); pending → 400
# =========================================================
def test_11_send_password_reset_user_with_password_sent_false(admin_headers):
    r = requests.post(
        f"{API}/users/{STATE['user1_id']}/send-password-reset",
        headers=admin_headers,
        json={"origin": BASE_URL},
        timeout=30,
    )
    # Email fails (fake domain) → 200 {sent:false, error}; token is created regardless
    assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text}"
    body = r.json()
    assert body["sent"] is False
    assert len(body["error"]) > 0


def test_12_send_password_reset_pending_user_400(admin_headers):
    r = requests.post(
        f"{API}/users/{STATE['user2_id']}/send-password-reset",
        headers=admin_headers,
        json={"origin": BASE_URL},
        timeout=30,
    )
    assert r.status_code == 400
    assert "Reenviar invitación" in r.json()["detail"] or "no ha establecido" in r.json()["detail"].lower()


def test_13_reset_token_works_in_set_password():
    """Generate a purpose=reset token directly and verify set-password consumes it."""
    async def _gen():
        import invitation_service
        db = _db()
        admin_doc = await db.users.find_one({"email": ADMIN_EMAIL}, {"id": 1, "_id": 0})
        return await invitation_service.create_token(db, STATE["user1_id"], "reset", admin_doc["id"])
    token = asyncio.run(_gen())

    r = requests.post(f"{API}/auth/validate-setup-token", json={"token": token}, timeout=30)
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["purpose"] == "reset"

    new_pw = "ResetPass456"
    r2 = requests.post(f"{API}/auth/set-password", json={"token": token, "password": new_pw}, timeout=30)
    assert r2.status_code == 200

    # login works
    r3 = requests.post(f"{API}/auth/login", json={"email": FAKE_INVITEE_1, "password": new_pw}, timeout=30)
    assert r3.status_code == 200
    STATE["user1_password"] = new_pw
    STATE["user1_login_token"] = r3.json()["access_token"]


# =========================================================
# 11. Change-password endpoint
# =========================================================
def test_14_change_password_wrong_current_returns_400():
    headers = {"Authorization": f"Bearer {STATE['user1_login_token']}", "Content-Type": "application/json"}
    r = requests.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword!!!", "new_password": "NewValidPass789"},
        timeout=30,
    )
    assert r.status_code == 400
    assert "incorrecta" in r.json()["detail"].lower()


def test_15_change_password_short_new_returns_400():
    headers = {"Authorization": f"Bearer {STATE['user1_login_token']}", "Content-Type": "application/json"}
    r = requests.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": STATE["user1_password"], "new_password": "short"},
        timeout=30,
    )
    assert r.status_code == 400
    assert "8 caracteres" in r.json()["detail"]


def test_16_change_password_success_and_login_with_new():
    headers = {"Authorization": f"Bearer {STATE['user1_login_token']}", "Content-Type": "application/json"}
    new_pw = "ChangedPass999"
    r = requests.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": STATE["user1_password"], "new_password": new_pw},
        timeout=30,
    )
    assert r.status_code == 200, r.text

    r2 = requests.post(f"{API}/auth/login", json={"email": FAKE_INVITEE_1, "password": new_pw}, timeout=30)
    assert r2.status_code == 200, r2.text
    STATE["user1_password"] = new_pw


# =========================================================
# 12. Recruiter permissions
# =========================================================
def test_17_recruiter_cannot_create_user(recruiter_headers):
    r = requests.post(
        f"{API}/users",
        headers=recruiter_headers,
        json={"email": FAKE_INVITEE_3, "name": "X", "role": "recruiter", "origin": BASE_URL},
        timeout=30,
    )
    assert r.status_code == 403, f"recruiter got {r.status_code}: {r.text}"


def test_18_recruiter_cannot_resend_invitation(recruiter_headers):
    r = requests.post(
        f"{API}/users/{STATE['user2_id']}/resend-invitation",
        headers=recruiter_headers,
        json={"origin": BASE_URL},
        timeout=30,
    )
    assert r.status_code == 403


# =========================================================
# 13. Activity logs
# =========================================================
def test_19_activity_logs_have_expected_actions():
    async def _check():
        db = _db()
        actions_needed = {"user_invited", "password_set", "password_changed"}
        # Look at recent logs
        logs = await db.activity_logs.find({"action": {"$in": list(actions_needed)}}).sort("timestamp", -1).limit(200).to_list(200)
        found = {l["action"] for l in logs}
        return found
    found = asyncio.run(_check())
    missing = {"user_invited", "password_set", "password_changed"} - found
    assert not missing, f"missing activity_logs actions: {missing}. found={found}"


# =========================================================
# 14. Regression: admin login + invalid google session
# =========================================================
def test_20_admin_login_regression():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200


def test_21_google_session_invalid_401():
    # POST /api/auth/google with invalid/fake session token should return 401
    r = requests.post(
        f"{API}/auth/google/session",
        json={"session_id": "invalid-session-xxx-fake"},
        timeout=30,
    )
    assert r.status_code in (401, 400), f"expected 401/400 for invalid google session, got {r.status_code}: {r.text}"
