"""Verifica el flujo de CV idénticos con fichas sintéticas (no toca datos reales)."""
import os
import sys
import uuid
import hashlib
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db

API = os.environ['API_URL']
EMAIL = os.environ['ADMIN_EMAIL']
PASSWORD = os.environ['ADMIN_PASSWORD']

db = get_db()
token = requests.post(f'{API}/api/auth/login', json={'email': EMAIL, 'password': PASSWORD}, timeout=30).json()['access_token']
H = {'Authorization': f'Bearer {token}'}

sha = hashlib.sha256(f'synthetic-{uuid.uuid4()}'.encode()).hexdigest()
keep_id, extra_id = f'test-keep-{uuid.uuid4()}', f'test-extra-{uuid.uuid4()}'
now = datetime.now(timezone.utc).isoformat()

db.candidates.insert_many([
    {'id': keep_id, 'full_name': 'ZZTest Identico', 'created_at': '2020-01-01T00:00:00+00:00',
     'skills': ['python'], 'resume_files': [{'file_path': f'p/{keep_id}', 'file_name': 'cv.pdf'}], 'is_deleted': False},
    {'id': extra_id, 'full_name': 'ZZTest Identico', 'created_at': '2021-01-01T00:00:00+00:00',
     'skills': ['python', 'sql'], 'presentation_subarea': 'Tesorería', 'email': 'zz@test.com',
     'resume_files': [{'file_path': f'p/{extra_id}', 'file_name': 'cv.pdf'}], 'is_deleted': False},
])
db.cv_hashes.insert_many([
    {'candidate_id': keep_id, 'file_path': f'p/{keep_id}', 'file_name': 'cv.pdf', 'sha256_file': sha,
     'sha256_text': None, 'active': True, 'upload_date': now},
    {'candidate_id': extra_id, 'file_path': f'p/{extra_id}', 'file_name': 'cv.pdf', 'sha256_file': sha,
     'sha256_text': None, 'active': True, 'upload_date': now},
])

try:
    groups = requests.get(f'{API}/api/duplicates/identical-cv', headers=H, timeout=120).json()['groups']
    group = next(g for g in groups if g['keep']['candidate_id'] == keep_id)
    assert group['status'] == 'safe', group['status']
    assert [e['candidate_id'] for e in group['extras']] == [extra_id]
    print('1. grupo detectado, conserva la mas antigua:', group['keep']['name'], 'OK')

    res = requests.post(f'{API}/api/duplicates/identical-cv/delete-extras', headers=H,
                        json={'group_keys': [group['group_key']]}, timeout=120).json()
    assert res['deleted_count'] == 1, res
    print('2. soft delete de sobrantes:', res['message'], '| campos copiados:', res['fields_filled'], 'OK')

    keep = db.candidates.find_one({'id': keep_id}, {'_id': 0})
    extra = db.candidates.find_one({'id': extra_id}, {'_id': 0})
    assert extra['is_deleted'] is True and extra['deletion_type'] == 'identical_cv_cleanup'
    assert extra['duplicate_of'] == keep_id
    assert keep['presentation_subarea'] == 'Tesorería' and keep['email'] == 'zz@test.com'
    assert sorted(keep['skills']) == ['python', 'sql']
    print('3. datos faltantes copiados y sobrante recuperable (is_deleted=True) OK')

    assert db.cv_hashes.count_documents({'candidate_id': extra_id, 'active': True}) == 0
    print('4. hash del sobrante desactivado OK')

    audit = db.cleanup_audit_log.find_one({'action': 'identical_cv_cleanup', 'kept_candidate_id': keep_id})
    assert audit and audit['candidate_ids'] == [extra_id]
    print('5. auditoria registrada OK')
finally:
    db.candidates.delete_many({'id': {'$in': [keep_id, extra_id]}})
    db.cv_hashes.delete_many({'candidate_id': {'$in': [keep_id, extra_id]}})
    db.cleanup_audit_log.delete_many({'kept_candidate_id': keep_id})
    print('limpieza de datos sinteticos OK')
