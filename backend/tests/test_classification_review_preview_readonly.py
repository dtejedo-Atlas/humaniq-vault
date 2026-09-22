"""Read-only checks against preview pending-classification endpoints (no mutations)."""

import os
import re
from typing import Any

import requests


def _read_admin_credentials() -> tuple[str, str]:
    content = open('/app/memory/test_credentials.md', 'r', encoding='utf-8').read()
    email_match = re.search(r"Admin .*?\n- \*\*Email:\*\*\s*([^\n]+)", content, re.DOTALL)
    password_match = re.search(r"Admin .*?\n- \*\*Email:\*\*[^\n]+\n- \*\*Password:\*\*\s*([^\n]+)", content, re.DOTALL)
    if not email_match or not password_match:
        raise AssertionError('No se pudieron leer credenciales admin desde /app/memory/test_credentials.md')
    return email_match.group(1).strip(), password_match.group(1).strip()


def _contains_object_id_key(payload: Any) -> bool:
    if isinstance(payload, dict):
        if '_id' in payload:
            return True
        return any(_contains_object_id_key(v) for v in payload.values())
    if isinstance(payload, list):
        return any(_contains_object_id_key(v) for v in payload)
    return False


def test_preview_pending_ids_match_paginated_pending_and_count_readonly():
    """Classification review queue: /pending, /pending/ids and /pending/count must stay in sync."""
    base_url = os.environ.get('REACT_APP_BACKEND_URL')
    assert base_url, 'REACT_APP_BACKEND_URL no está configurada'
    api = base_url.rstrip('/') + '/api'

    email, password = _read_admin_credentials()
    login = requests.post(
        f'{api}/auth/login',
        json={'email': email, 'password': password},
        timeout=20,
    )
    assert login.status_code == 200, f'Login falló: {login.status_code} {login.text[:300]}'
    token = login.json().get('access_token')
    assert token, 'No se recibió access_token'
    headers = {'Authorization': f'Bearer {token}'}

    first = requests.get(
        f'{api}/atlas/classifications/pending',
        params={'page': 1, 'limit': 20},
        headers=headers,
        timeout=20,
    )
    assert first.status_code == 200, f'/pending falló: {first.status_code} {first.text[:300]}'
    first_data = first.json()
    assert not _contains_object_id_key(first_data), 'Respuesta /pending contiene _id'

    pages = first_data.get('pages', 0)
    total = first_data.get('total', 0)
    paginated_ids = []

    for page in range(1, max(1, pages) + 1):
        resp = requests.get(
            f'{api}/atlas/classifications/pending',
            params={'page': page, 'limit': 20},
            headers=headers,
            timeout=20,
        )
        assert resp.status_code == 200, f'/pending?page={page} falló: {resp.status_code}'
        data = resp.json()
        assert not _contains_object_id_key(data), f'Respuesta /pending?page={page} contiene _id'
        for candidate in data.get('candidates', []):
            current = candidate.get('current_classification') or {}
            proposed = candidate.get('proposed_classification') or {}
            assert 'years_experience' in current, 'current_classification sin years_experience'
            assert 'years_experience' in proposed, 'proposed_classification sin years_experience'
            paginated_ids.append(candidate.get('id'))

    ids_resp = requests.get(f'{api}/atlas/classifications/pending/ids', headers=headers, timeout=20)
    assert ids_resp.status_code == 200, f'/pending/ids falló: {ids_resp.status_code} {ids_resp.text[:300]}'
    ids_data = ids_resp.json()
    assert not _contains_object_id_key(ids_data), 'Respuesta /pending/ids contiene _id'
    endpoint_ids = ids_data.get('candidate_ids') or []

    count_resp = requests.get(f'{api}/atlas/classifications/pending/count', headers=headers, timeout=20)
    assert count_resp.status_code == 200, f'/pending/count falló: {count_resp.status_code}'
    count_data = count_resp.json()
    assert not _contains_object_id_key(count_data), 'Respuesta /pending/count contiene _id'
    count_value = count_data.get('count')

    assert len(set(paginated_ids)) == total
    assert len(endpoint_ids) == ids_data.get('total')
    assert set(endpoint_ids) == set(paginated_ids)
    assert count_value == total == ids_data.get('total')
