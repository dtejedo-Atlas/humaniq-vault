"""Read-only public preview checks: admin login, auth/me, and candidate read."""

import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values


def _extract_admin_credentials() -> tuple[str, str]:
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    email_match = re.search(r"Admin \(testing\).*?\*\*Email:\*\*\s*([^\n]+)", content, re.S)
    password_match = re.search(r"Admin \(testing\).*?\*\*Password:\*\*\s*([^\n]+)", content, re.S)
    assert email_match and password_match, "No se encontraron credenciales admin en /app/memory/test_credentials.md"
    return email_match.group(1).strip(), password_match.group(1).strip()


def _base_url() -> str:
    env = dotenv_values("/app/frontend/.env")
    base = env.get("REACT_APP_BACKEND_URL")
    assert base, "REACT_APP_BACKEND_URL no configurada en frontend/.env"
    return base.rstrip("/")


# Module: public preview read-only verification for Option A request
def test_admin_login_auth_me_and_candidate_readonly_preview():
    base = _base_url()
    email, password = _extract_admin_credentials()

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    login = session.post(
        f"{base}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert login.status_code == 200
    token = login.json().get("access_token")
    assert isinstance(token, str) and len(token) > 10

    session.headers.update({"Authorization": f"Bearer {token}"})
    auth_me = session.get(f"{base}/api/auth/me", timeout=30)
    assert auth_me.status_code == 200
    me = auth_me.json()
    assert me.get("email") == email
    assert me.get("role") == "admin"

    candidates = session.get(f"{base}/api/candidates", params={"limit": 1}, timeout=30)
    assert candidates.status_code == 200
    rows = candidates.json()
    assert isinstance(rows, list)

    if not rows:
        pytest.skip("No hay candidatos en preview para validar lectura de detalle")

    candidate_id = rows[0]["id"]
    read_detail = session.get(f"{base}/api/candidates/{candidate_id}", timeout=30)
    assert read_detail.status_code == 200
    detail = read_detail.json()
    assert detail.get("id") == candidate_id
