"""Isolated-DB tests for Humaniq taxonomy acceptance criteria.

Covers: PATCH /api/atlas/classifications/manual normalization (English/casing/legacy keys),
presentation_* fields save+return, subarea validation, salud/sustentabilidad null engine_area,
unrecognized values, and Job create/update taxonomy normalization.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

import server  # noqa: E402
from models import User, UserRole  # noqa: E402


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
async def isolated_db():
    mongo_url = os.environ.get('MONGO_URL')
    assert mongo_url, 'MONGO_URL required'
    db_name = f"test_humaniq_{uuid.uuid4().hex[:10]}"
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[db_name]

    original_db = server.db
    original_bp = server.background_processor.db
    server.db = test_db
    server.background_processor.db = test_db

    await test_db.industries.insert_many([
        {'key': 'test_industry_one', 'name_es': 'Industria Test'},
    ])
    # Legacy custom area (admin-created) for regression test
    await test_db.functional_areas.insert_many([
        {'key': 'test_legacy_area', 'name_es': 'Área Legacy'},
    ])
    try:
        yield test_db
    finally:
        server.db = original_db
        server.background_processor.db = original_bp
        server.app.dependency_overrides.clear()
        await client.drop_database(db_name)
        client.close()


@pytest.fixture
async def api_client(isolated_db):
    fake_user = User(id='t-admin', email='t@x.com', name='T', role=UserRole.ADMIN)
    server.app.dependency_overrides[server.get_current_user] = lambda: fake_user

    # Some endpoints (e.g. /jobs) invoke get_current_user manually with credentials
    # instead of via Depends, so we monkeypatch the module-level function too.
    async def _fake_get_current_user(*args, **kwargs):
        return fake_user
    original_gcu = server.get_current_user
    server.get_current_user = _fake_get_current_user
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver',
                                  headers={'Authorization': 'Bearer fake'}) as client:
        yield client
    server.get_current_user = original_gcu


async def _insert(db, cid, **extra):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        'id': cid,
        'full_name': f'TEST {cid}',
        'industry': 'test_industry_one',
        'functional_area': None,
        'seniority': None,
        'years_experience': None,
        'ai_classification': {'approved_by_recruiter': False, 'confidence_score': 0.2},
        'is_deleted': False,
        'created_at': now,
        'updated_at': now,
    }
    doc.update(extra)
    await db.candidates.insert_one(doc)


# ---------------------------------------------------------------------------
# Normalization: English / casing / legacy keys should NOT return 422
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("input_val,expected_engine", [
    ("IT", "technology"),
    ("Manufacturing", "operations"),
    ("customer service", "operations"),
    ("accounting", "finance"),
])
async def test_manual_patch_normalizes_legacy_and_english(api_client, isolated_db, input_val, expected_engine):
    cid = f"cand-norm-{input_val.replace(' ','_')}"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}',
                                json={'functional_area': input_val})
    assert r.status_code == 200, f"input={input_val} status={r.status_code} body={r.text}"
    body = r.json()
    assert body['functional_area'] == expected_engine, f"input={input_val} got={body.get('functional_area')}"
    doc = await isolated_db.candidates.find_one({'id': cid}, {'_id': 0})
    ai = doc['ai_classification']
    # presentation_area should be populated
    assert ai.get('presentation_area'), f"presentation_area empty: {ai}"


# ---------------------------------------------------------------------------
# presentation_* fields accepted and returned
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_manual_patch_accepts_presentation_fields(api_client, isolated_db):
    cid = "cand-pres"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}', json={
        'presentation_area': 'finanzas',
        'presentation_subarea': 'contraloria',
        'presentation_seniority': 'gerencia',
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['functional_area'] == 'finance'
    assert body['seniority'] == 'manager'
    doc = await isolated_db.candidates.find_one({'id': cid}, {'_id': 0})
    ai = doc['ai_classification']
    assert ai.get('presentation_area') == 'finanzas'
    assert ai.get('presentation_subarea') == 'contraloria'
    assert ai.get('presentation_seniority') == 'gerencia'


# ---------------------------------------------------------------------------
# Subarea validation: invalid subarea for area → dropped; valid → saved
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_subarea_invalid_for_area_is_dropped(api_client, isolated_db):
    cid = "cand-sub-bad"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}', json={
        'presentation_area': 'finanzas',
        'presentation_subarea': 'reclutamiento',  # belongs to recursos_humanos
    })
    assert r.status_code == 200, r.text
    doc = await isolated_db.candidates.find_one({'id': cid}, {'_id': 0})
    ai = doc['ai_classification']
    assert ai.get('presentation_area') == 'finanzas'
    assert ai.get('presentation_subarea') is None, f"invalid subarea leaked: {ai.get('presentation_subarea')}"


@pytest.mark.anyio
async def test_subarea_valid_for_area_is_saved(api_client, isolated_db):
    cid = "cand-sub-ok"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}', json={
        'presentation_area': 'finanzas',
        'presentation_subarea': 'contraloria',
    })
    assert r.status_code == 200
    doc = await isolated_db.candidates.find_one({'id': cid}, {'_id': 0})
    assert doc['ai_classification'].get('presentation_subarea') == 'contraloria'


# ---------------------------------------------------------------------------
# salud/sustentabilidad → engine null, preserved, approval not blocked
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_salud_saves_null_engine_and_keeps_presentation(api_client, isolated_db):
    cid = "cand-salud"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}', json={
        'presentation_area': 'salud',
        'presentation_seniority': 'gerencia',
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['functional_area'] is None
    doc = await isolated_db.candidates.find_one({'id': cid}, {'_id': 0})
    ai = doc['ai_classification']
    assert ai.get('presentation_area') == 'salud'
    assert doc.get('functional_area') is None


@pytest.mark.anyio
async def test_approval_not_blocked_for_salud(api_client, isolated_db):
    cid = "cand-salud-approve"
    await _insert(isolated_db, cid, industry='test_industry_one', seniority='manager',
                  ai_classification={
                      'industry': 'test_industry_one',
                      'functional_area': None,
                      'seniority': 'manager',
                      'presentation_area': 'salud',
                      'presentation_seniority': 'gerencia',
                      'approved_by_recruiter': False,
                      'confidence_score': 0.8,
                      'source': 'atlas_ai',
                  })
    r = await api_client.post(f'/api/atlas/approve-classification/{cid}')
    # Should NOT return 400 "campos incompletos"; expect 200
    assert r.status_code == 200, f"status={r.status_code} body={r.text}"


# ---------------------------------------------------------------------------
# Unrecognized value → functional_area null, marked for review
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_unrecognized_value_not_saved_as_engine(api_client, isolated_db):
    cid = "cand-unk"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}', json={
        'functional_area': 'astrología',
    })
    # Either 422 (fuera de catálogo) or 200 with null saved; the requirement is that
    # engine field is NOT contaminated.
    if r.status_code == 200:
        doc = await isolated_db.candidates.find_one({'id': cid}, {'_id': 0})
        assert doc.get('functional_area') in (None, ''), doc.get('functional_area')
    else:
        assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Regression: legacy custom area from functional_areas collection is accepted
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_legacy_custom_area_still_accepted(api_client, isolated_db):
    cid = "cand-legacy-custom"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}',
                                json={'functional_area': 'test_legacy_area'})
    assert r.status_code == 200, r.text
    assert r.json()['functional_area'] == 'test_legacy_area'


@pytest.mark.anyio
async def test_totally_unknown_area_returns_422(api_client, isolated_db):
    cid = "cand-really-unknown"
    await _insert(isolated_db, cid)
    r = await api_client.patch(f'/api/atlas/classifications/manual/{cid}',
                                json={'functional_area': 'zzz_not_in_any_catalog'})
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Job create/update normalizes taxonomy
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_job_create_normalizes_presentation_area_and_seniority(api_client):
    payload = {
        'title': 'TEST Job Humaniq',
        'company': 'TEST Co',
        'industry': 'test_industry_one',
        'functional_area': 'manufactura',
        'seniority': 'gerencia',
        'description': 'test description',
        'presentation_area': 'manufactura',
        'presentation_seniority': 'gerencia',
    }
    r = await api_client.post('/api/jobs', json=payload)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body.get('functional_area') == 'operations', body
    assert body.get('seniority') == 'manager', body
    assert body.get('presentation_area') == 'manufactura'
    assert body.get('presentation_seniority') == 'gerencia'


@pytest.mark.anyio
async def test_job_create_accepts_spanish_label(api_client):
    payload = {
        'title': 'TEST Job Label',
        'company': 'TEST Co',
        'industry': 'test_industry_one',
        'functional_area': 'Manufactura / Producción',
        'seniority': 'gerencia',
        'description': 'test description',
    }
    r = await api_client.post('/api/jobs', json=payload)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body.get('functional_area') == 'operations', body
    assert body.get('seniority') == 'manager', body


@pytest.mark.anyio
async def test_job_update_normalizes(api_client):
    create = await api_client.post('/api/jobs', json={
        'title': 'TEST Upd',
        'company': 'TEST Co',
        'industry': 'test_industry_one',
        'functional_area': 'finance',
        'seniority': 'senior',
        'description': 'x',
    })
    assert create.status_code in (200, 201), create.text
    jid = create.json().get('id')
    r = await api_client.put(f'/api/jobs/{jid}', json={
        'presentation_area': 'ventas',
        'presentation_seniority': 'direccion',
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get('functional_area') == 'sales'
    assert body.get('seniority') == 'director'
