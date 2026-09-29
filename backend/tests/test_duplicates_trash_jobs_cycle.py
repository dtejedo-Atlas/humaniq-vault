"""Pruebas del ciclo: eliminar duplicados, papelera, archivo de vacantes y cron."""
import os
import sys
import uuid
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db

API = os.environ['API_URL']
db = get_db()
token = requests.post(f'{API}/api/auth/login',
                      json={'email': os.environ['ADMIN_EMAIL'], 'password': os.environ['ADMIN_PASSWORD']},
                      timeout=60).json()['access_token']
H = {'Authorization': f'Bearer {token}'}

clean_ids = []
job_id = None
try:
    # ---------- 1. Eliminar ficha sin datos propios + papelera ----------
    plain_id = f'test-del-{uuid.uuid4()}'
    rich_id = f'test-rich-{uuid.uuid4()}'
    clean_ids += [plain_id, rich_id]
    db.candidates.insert_many([
        {'id': plain_id, 'full_name': 'ZZTest Sin Datos', 'created_at': '2024-01-01T00:00:00+00:00', 'is_deleted': False},
        {'id': rich_id, 'full_name': 'ZZTest Con Notas', 'created_at': '2024-01-01T00:00:00+00:00', 'is_deleted': False,
         'notes': [{'id': 'n1', 'note_text': 'nota', 'created_at': '2024-01-02T00:00:00+00:00'}]},
    ])
    res = requests.post(f'{API}/api/duplicates/delete-candidates', headers=H,
                        json={'candidate_ids': [plain_id, rich_id]}, timeout=60).json()
    assert res['deleted_count'] == 1 and res['deleted'][0]['candidate_id'] == plain_id, res
    assert res['blocked'][0]['candidate_id'] == rich_id and res['blocked'][0]['reason'] == 'tiene_datos_propios', res
    print('1. eliminar duplicado: sobrante eliminado, ficha con notas BLOQUEADA OK')

    trash = requests.get(f'{API}/api/trash/candidates', headers=H, timeout=60).json()
    entry = next(c for c in trash['candidates'] if c['candidate_id'] == plain_id)
    assert entry['deletion_type'] == 'duplicate_manual' and entry['deleted_by'] and entry['reason']
    print('2. papelera muestra fecha, autor y motivo:', entry['deleted_at'][:10], '|', entry['deleted_by'], '|', entry['reason'], 'OK')

    restore = requests.post(f'{API}/api/candidates/{plain_id}/restore', headers=H, timeout=60)
    assert restore.status_code == 200, restore.text
    assert db.candidates.find_one({'id': plain_id}).get('is_deleted') is None
    print('3. restaurar desde papelera OK')

    # ---------- 2. Vacantes: archivar / reactivar / similares / reutilizar ----------
    job_id = f'test-job-{uuid.uuid4()}'
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    db.jobs.insert_one({
        'id': job_id, 'title': 'ZZTest Gerente de Tesorería', 'company': 'ZZ Test SA',
        'industry': 'finance', 'functional_area': 'finance', 'seniority': 'manager',
        'presentation_area': 'Finanzas', 'presentation_subarea': 'Tesorería',
        'status': 'active', 'created_at': old, 'updated_at': old, 'created_by': 'test',
    })
    assigned_id = f'test-cand-{uuid.uuid4()}'
    clean_ids.append(assigned_id)
    db.candidates.insert_one({
        'id': assigned_id, 'full_name': 'ZZTest Candidato Asignado', 'is_deleted': False,
        'created_at': old, 'current_title': 'Tesorero',
        'job_assignments': [{'job_id': job_id, 'stage': 'interviewed', 'assigned_by': 'test',
                             'assigned_at': old, 'updated_at': old}],
    })

    report = requests.get(f'{API}/api/jobs/expiring', headers=H, timeout=60).json()
    assert any(j['id'] == job_id for j in report['expired']), 'la vacante inactiva debe salir como caducada'
    print('4. caducidad: vacante con 200 días sin actividad detectada como caducada OK')

    arch = requests.post(f'{API}/api/jobs/{job_id}/archive', headers=H, json={}, timeout=60)
    assert arch.status_code == 200, arch.text
    active_jobs = requests.get(f'{API}/api/jobs', headers=H, timeout=60).json()
    assert all(j['id'] != job_id for j in active_jobs), 'la archivada no debe salir en el listado por defecto'
    archived_jobs = requests.get(f'{API}/api/jobs', headers=H, params={'status': 'archived'}, timeout=60).json()
    assert any(j['id'] == job_id for j in archived_jobs), 'debe salir con el filtro de archivadas'
    stored = db.candidates.find_one({'id': assigned_id})
    assert stored['job_assignments'][0]['stage'] == 'interviewed', 'la archivada conserva candidatos y etapas'
    print('5. archivar: fuera del listado activo, visible en "Ver archivadas", candidatos y etapas intactos OK')

    similar = requests.get(f'{API}/api/jobs/similar-archived', headers=H, timeout=60, params={
        'title': 'Gerente de Tesorería', 'presentation_area': 'Finanzas', 'presentation_subarea': 'Tesorería',
    }).json()
    match = next(j for j in similar['jobs'] if j['id'] == job_id)
    assert any(c['id'] == assigned_id for c in match['candidates']), match
    print('6. sugerencia de archivadas similares con sus candidatos OK:', match['match_reasons'])

    new_job_id = f'test-job-new-{uuid.uuid4()}'
    db.jobs.insert_one({'id': new_job_id, 'title': 'ZZTest Gerente de Tesorería 2', 'industry': 'finance',
                        'functional_area': 'finance', 'seniority': 'manager', 'status': 'active',
                        'created_at': datetime.now(timezone.utc).isoformat(), 'created_by': 'test'})
    reuse = requests.post(f'{API}/api/jobs/{new_job_id}/reuse-candidates', headers=H, timeout=60,
                          json={'source_job_id': job_id, 'candidate_ids': [assigned_id]}).json()
    assert len(reuse['assigned']) == 1, reuse
    refreshed = db.candidates.find_one({'id': assigned_id})
    assert any(a['job_id'] == new_job_id for a in refreshed['job_assignments'])
    db.jobs.delete_one({'id': new_job_id})
    print('7. reutilizar candidatos de archivada en vacante nueva OK')

    react = requests.post(f'{API}/api/jobs/{job_id}/reactivate', headers=H, timeout=60)
    assert react.status_code == 200 and db.jobs.find_one({'id': job_id})['status'] == 'active'
    print('8. reactivar vacante OK')

    # ---------- 3. Cron de auto-archivo ----------
    unauth = requests.post(f'{API}/api/cron/archive-stale-jobs', json={}, timeout=60)
    assert unauth.status_code == 401, unauth.status_code
    secret = [l.split('=', 1)[1].strip().strip('"') for l in open('/app/backend/.env') if l.startswith('WEBHOOK_CRON_SECRET')][0]
    run_id = str(uuid.uuid4())
    ok = requests.post(f'{API}/api/cron/archive-stale-jobs', timeout=60,
                       headers={'Authorization': f'Bearer {secret}'},
                       json={'event': 'schedule.triggered', 'run_id': run_id})
    assert ok.status_code == 200 and ok.json()['accepted'], ok.text
    dup = requests.post(f'{API}/api/cron/archive-stale-jobs', timeout=60,
                        headers={'Authorization': f'Bearer {secret}'},
                        json={'event': 'schedule.triggered', 'run_id': run_id}).json()
    assert dup.get('duplicate') is True, dup
    print('9. cron: 401 sin token, 200 con token, idempotente por run_id OK')

    import time
    db.jobs.update_one({'id': job_id}, {'$set': {'updated_at': old, 'created_at': old},
                                        '$unset': {'last_activity_at': ''}})
    db.candidates.update_one({'id': assigned_id}, {'$set': {'job_assignments.$[].updated_at': old}})
    db.activity_logs.delete_many({'entity_type': 'job', 'entity_id': job_id})
    requests.post(f'{API}/api/cron/archive-stale-jobs', timeout=60,
                  headers={'Authorization': f'Bearer {secret}'},
                  json={'event': 'schedule.triggered', 'run_id': str(uuid.uuid4())})
    time.sleep(4)
    assert db.jobs.find_one({'id': job_id})['status'] == 'archived', 'el cron debe archivar la vacante caducada'
    print('10. auto-archivo por 90 días sin actividad ejecutado OK')
finally:
    db.candidates.delete_many({'id': {'$in': clean_ids}})
    if job_id:
        db.jobs.delete_many({'id': {'$regex': '^test-job-'}})
    db.cleanup_audit_log.delete_many({'candidate_ids': {'$in': clean_ids}})
    db.activity_logs.delete_many({'entity_id': {'$in': clean_ids + ([job_id] if job_id else [])}})
    print('limpieza de datos sinteticos OK')
