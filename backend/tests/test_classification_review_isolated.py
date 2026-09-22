"""Tests aislados (Mongo local temporal) para revisión/edición/aprobación de clasificaciones."""

import asyncio
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
    """MongoDB LOCAL aislado por prueba; nunca toca Atlas compartido."""
    mongo_url = os.environ.get('MONGO_URL')
    assert mongo_url, 'MONGO_URL no configurada'

    db_name = f"test_class_review_{uuid.uuid4().hex[:10]}"
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[db_name]

    original_db = server.db
    original_bp_db = server.background_processor.db
    server.db = test_db
    server.background_processor.db = test_db

    await test_db.industries.insert_many([
        {'key': 'test_industry_one', 'name_es': 'Industria Test 1'},
        {'key': 'test_industry_two', 'name_es': 'Industria Test 2'},
    ])
    await test_db.functional_areas.insert_many([
        {'key': 'test_area_one', 'name_es': 'Área Test 1'},
        {'key': 'test_area_two', 'name_es': 'Área Test 2'},
    ])

    try:
        yield test_db
    finally:
        server.db = original_db
        server.background_processor.db = original_bp_db
        server.app.dependency_overrides.clear()
        await client.drop_database(db_name)
        client.close()


@pytest.fixture
async def api_client(isolated_db):
    """Cliente ASGI sin lifespan/startup para evitar side-effects globales."""
    fake_user = User(
        id='test-admin',
        email='test-admin@example.com',
        name='Test Admin',
        role=UserRole.ADMIN,
    )

    def _override_user():
        return fake_user

    server.app.dependency_overrides[server.get_current_user] = _override_user
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        yield client


async def _insert_candidate(db, candidate_id: str, **extra):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        'id': candidate_id,
        'full_name': f'TEST {candidate_id}',
        'industry': None,
        'functional_area': None,
        'seniority': None,
        'years_experience': None,
        'ai_classification': None,
        'is_deleted': False,
        'created_at': now,
        'updated_at': now,
    }
    doc.update(extra)
    await db.candidates.insert_one(doc)


# Feature: PATCH /api/atlas/classifications/manual/{id}


@pytest.mark.anyio
async def test_manual_patch_empty_body_returns_400(api_client):
    response = await api_client.patch('/api/atlas/classifications/manual/missing', json={})
    assert response.status_code == 400
    assert 'No hay cambios' in response.json()['detail']


@pytest.mark.anyio
async def test_manual_patch_missing_or_deleted_returns_404(api_client, isolated_db):
    await _insert_candidate(isolated_db, 'cand-deleted', is_deleted=True)

    response_missing = await api_client.patch('/api/atlas/classifications/manual/cand-missing', json={'industry': 'test_industry_one'})
    response_deleted = await api_client.patch('/api/atlas/classifications/manual/cand-deleted', json={'industry': 'test_industry_one'})

    assert response_missing.status_code == 404
    assert response_deleted.status_code == 404


@pytest.mark.anyio
async def test_manual_patch_approved_returns_409(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        'cand-approved',
        ai_classification={'approved_by_recruiter': True, 'confidence_score': 0.32, 'source': 'atlas_ai'},
    )

    response = await api_client.patch('/api/atlas/classifications/manual/cand-approved', json={'industry': 'test_industry_one'})
    assert response.status_code == 409


@pytest.mark.anyio
async def test_manual_patch_saves_only_present_fields_and_preserves_metadata(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        'cand-meta',
        industry='legacy_industry',
        functional_area='legacy_area',
        seniority='junior',
        years_experience=7,
        ai_classification={
            'industry': 'legacy_industry',
            'functional_area': 'legacy_area',
            'seniority': 'junior',
            'confidence_score': 0.44,
            'source': 'atlas_ai',
            'classified_at': '2025-01-01T00:00:00+00:00',
            'approved_by_recruiter': False,
            'extra_meta': 'must_stay',
        },
    )

    response = await api_client.patch('/api/atlas/classifications/manual/cand-meta', json={'industry': 'test_industry_one'})
    assert response.status_code == 200
    body = response.json()
    assert body['industry'] == 'test_industry_one'
    assert body['functional_area'] == 'legacy_area'
    assert body['seniority'] == 'junior'
    assert body['years_experience'] == 7

    doc = await isolated_db.candidates.find_one({'id': 'cand-meta'}, {'_id': 0})
    ai = doc['ai_classification']
    assert ai['confidence_score'] == 0.44
    assert ai['source'] == 'atlas_ai'
    assert ai['extra_meta'] == 'must_stay'
    assert ai['approved_by_recruiter'] is False
    assert ai.get('was_corrected') is True
    assert ai.get('manually_edited_by') == 'test-admin'
    assert ai.get('manual_fields', {}).get('industry') == 'test_industry_one'


@pytest.mark.anyio
async def test_manual_patch_supports_null_and_zero_years(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        'cand-null-zero',
        industry='test_industry_one',
        years_experience=9,
        ai_classification={'approved_by_recruiter': False, 'confidence_score': 0.2},
    )

    clear_industry = await api_client.patch('/api/atlas/classifications/manual/cand-null-zero', json={'industry': None})
    set_zero_years = await api_client.patch('/api/atlas/classifications/manual/cand-null-zero', json={'years_experience': 0})

    assert clear_industry.status_code == 200
    assert set_zero_years.status_code == 200
    assert clear_industry.json()['industry'] is None
    assert set_zero_years.json()['years_experience'] == 0


@pytest.mark.anyio
async def test_manual_patch_years_validation_strict(api_client, isolated_db):
    await _insert_candidate(isolated_db, 'cand-years-val', ai_classification={'approved_by_recruiter': False})

    bad_text = await api_client.patch('/api/atlas/classifications/manual/cand-years-val', json={'years_experience': '0'})
    bad_negative = await api_client.patch('/api/atlas/classifications/manual/cand-years-val', json={'years_experience': -1})
    bad_upper = await api_client.patch('/api/atlas/classifications/manual/cand-years-val', json={'years_experience': 101})

    assert bad_text.status_code == 422
    assert bad_negative.status_code == 422
    assert bad_upper.status_code == 422


@pytest.mark.anyio
async def test_manual_patch_invalid_catalog_returns_422(api_client, isolated_db):
    await _insert_candidate(isolated_db, 'cand-bad-catalog', ai_classification={'approved_by_recruiter': False})
    response = await api_client.patch('/api/atlas/classifications/manual/cand-bad-catalog', json={'industry': 'not_catalog'})
    assert response.status_code == 422
    assert 'fuera del catálogo' in response.json()['detail']


@pytest.mark.anyio
async def test_manual_patch_ai_null_supported_and_not_approved(api_client, isolated_db):
    await _insert_candidate(isolated_db, 'cand-ai-null', ai_classification=None)

    response = await api_client.patch(
        '/api/atlas/classifications/manual/cand-ai-null',
        json={'industry': 'test_industry_two', 'functional_area': 'test_area_one', 'seniority': 'manager'},
    )
    assert response.status_code == 200

    doc = await isolated_db.candidates.find_one({'id': 'cand-ai-null'}, {'_id': 0, 'ai_classification': 1})
    ai = doc['ai_classification']
    assert ai['approved_by_recruiter'] is False
    assert ai['source'] == 'manual_draft'
    assert ai['confidence_score'] == 0.0


@pytest.mark.anyio
async def test_manual_patch_concurrent_edits_preserve_both_fields(api_client, isolated_db):
    await _insert_candidate(isolated_db, 'cand-concurrent', ai_classification={'approved_by_recruiter': False, 'confidence_score': 0.1})

    async def patch_industry():
        return await api_client.patch('/api/atlas/classifications/manual/cand-concurrent', json={'industry': 'test_industry_one'})

    async def patch_area():
        return await api_client.patch('/api/atlas/classifications/manual/cand-concurrent', json={'functional_area': 'test_area_two'})

    r1, r2 = await asyncio.gather(patch_industry(), patch_area())
    assert r1.status_code == 200
    assert r2.status_code == 200

    doc = await isolated_db.candidates.find_one({'id': 'cand-concurrent'}, {'_id': 0, 'industry': 1, 'functional_area': 1, 'ai_classification.manual_fields': 1})
    assert doc['industry'] == 'test_industry_one'
    assert doc['functional_area'] == 'test_area_two'
    assert doc['ai_classification']['manual_fields']['industry'] == 'test_industry_one'
    assert doc['ai_classification']['manual_fields']['functional_area'] == 'test_area_two'


# Feature: approve individual y bulk (sin LLM, con fixtures sintéticos)


@pytest.mark.anyio
async def test_approve_single_valid_and_preserves_years(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        'cand-approve-ok',
        years_experience=12,
        ai_classification={
            'industry': 'test_industry_one',
            'functional_area': 'test_area_one',
            'seniority': 'manager',
            'confidence_score': 0.51,
            'approved_by_recruiter': False,
            'source': 'atlas_ai',
        },
    )

    response = await api_client.post('/api/atlas/approve-classification/cand-approve-ok')
    assert response.status_code == 200

    doc = await isolated_db.candidates.find_one({'id': 'cand-approve-ok'}, {'_id': 0, 'years_experience': 1, 'ai_classification': 1})
    assert doc['years_experience'] == 12
    assert doc['ai_classification']['approved_by_recruiter'] is True


@pytest.mark.anyio
async def test_approve_single_rejects_incomplete_or_noncanonical(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        'cand-approve-bad',
        ai_classification={
            'industry': 'not_catalog',
            'functional_area': 'test_area_one',
            'seniority': 'manager',
            'confidence_score': 0.4,
            'approved_by_recruiter': False,
        },
    )
    bad = await api_client.post('/api/atlas/approve-classification/cand-approve-bad')
    assert bad.status_code == 422

    await _insert_candidate(
        isolated_db,
        'cand-approve-incomplete',
        ai_classification={'industry': 'test_industry_one', 'functional_area': None, 'seniority': 'manager', 'approved_by_recruiter': False},
    )
    incomplete = await api_client.post('/api/atlas/approve-classification/cand-approve-incomplete')
    assert incomplete.status_code == 422


@pytest.mark.anyio
async def test_bulk_approve_partial_errors_keep_failed_pending(api_client, isolated_db):
    await _insert_candidate(
        isolated_db,
        'cand-bulk-good',
        years_experience=0,
        ai_classification={
            'industry': 'test_industry_two',
            'functional_area': 'test_area_two',
            'seniority': 'senior',
            'confidence_score': 0.49,
            'approved_by_recruiter': False,
        },
    )
    await _insert_candidate(
        isolated_db,
        'cand-bulk-bad',
        ai_classification={
            'industry': 'not_catalog',
            'functional_area': 'test_area_two',
            'seniority': 'senior',
            'confidence_score': 0.49,
            'approved_by_recruiter': False,
        },
    )

    response = await api_client.post(
        '/api/atlas/classifications/bulk-approve',
        json={'candidate_ids': ['cand-bulk-good', 'cand-bulk-bad']},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['approved_count'] == 1
    assert len(body['errors']) == 1
    assert body['errors'][0]['id'] == 'cand-bulk-bad'

    good = await isolated_db.candidates.find_one({'id': 'cand-bulk-good'}, {'_id': 0, 'years_experience': 1, 'ai_classification.approved_by_recruiter': 1})
    bad = await isolated_db.candidates.find_one({'id': 'cand-bulk-bad'}, {'_id': 0, 'ai_classification.approved_by_recruiter': 1})
    assert good['years_experience'] == 0
    assert good['ai_classification']['approved_by_recruiter'] is True
    assert bad['ai_classification']['approved_by_recruiter'] is False

    pending_ids = await api_client.get('/api/atlas/classifications/pending/ids')
    assert pending_ids.status_code == 200
    assert 'cand-bulk-bad' in pending_ids.json()['candidate_ids']


@pytest.mark.anyio
async def test_bulk_approve_empty_payload_returns_400(api_client):
    response = await api_client.post('/api/atlas/classifications/bulk-approve', json={'candidate_ids': []})
    assert response.status_code == 400
