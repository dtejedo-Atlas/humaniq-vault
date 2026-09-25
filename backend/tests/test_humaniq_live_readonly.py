"""Live read-only checks against preview API for Humaniq taxonomy endpoints.

Only performs GETs and Ángel candidate read verification. No writes.
"""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASSWORD = "+OipyxbpGdvQIB9FNTF#D$"

ANGEL_ID = "ee7dd8a7-9611-4cf0-979c-0f8b6827224d"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_taxonomy_humaniq_shape(auth_headers):
    r = requests.get(f"{BASE}/api/taxonomy/humaniq", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # top-level keys
    areas = data.get("areas") or data.get("functional_areas") or []
    senior = data.get("seniority_levels") or data.get("seniorities") or []
    assert len(areas) == 15, f"Expected 15 areas got {len(areas)}: keys={[a.get('key') for a in areas]}"
    # Count subareas
    total_sub = sum(len(a.get("subareas", [])) for a in areas)
    assert total_sub == 105, f"Expected 105 subareas got {total_sub}"
    assert len(senior) == 13, f"Expected 13 seniorities got {len(senior)}"

    # Verify null engine_area only for salud and sustentabilidad
    null_engine = [a["key"] for a in areas if a.get("engine_area") is None]
    assert set(null_engine) == {"salud", "sustentabilidad"}, f"Unexpected null engine areas: {null_engine}"

    # seniority ranks 1..13
    ranks = sorted([s.get("rank") for s in senior])
    assert ranks == list(range(1, 14)), f"Ranks: {ranks}"
    for s in senior:
        assert s.get("engine_seniority"), f"Missing engine_seniority for {s}"


def test_taxonomy_lookup_includes_engine_labels(auth_headers):
    r = requests.get(f"{BASE}/api/taxonomy/lookup", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    # sanity - result should be non-empty json
    assert isinstance(data, dict) and len(data) > 0


def test_angel_candidate_state(auth_headers):
    r = requests.get(f"{BASE}/api/candidates/{ANGEL_ID}", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c.get("functional_area") == "finance", f"functional_area={c.get('functional_area')}"
    ai = c.get("ai_classification") or {}
    assert ai.get("presentation_area") == "finanzas", f"presentation_area={ai.get('presentation_area')}"
    assert ai.get("presentation_subarea") == "contraloria", f"presentation_subarea={ai.get('presentation_subarea')}"
    assert ai.get("presentation_seniority") == "gerencia", f"presentation_seniority={ai.get('presentation_seniority')}"
