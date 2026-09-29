"""Fusión N-a-1 por tandas de los grupos de duplicados con el mismo email. Autorizada por el usuario."""
import json
import os
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db

API = os.environ['API_URL']
BATCH_SIZE = 5

db = get_db()
token = requests.post(f'{API}/api/auth/login',
                      json={'email': os.environ['ADMIN_EMAIL'], 'password': os.environ['ADMIN_PASSWORD']},
                      timeout=60).json()['access_token']
H = {'Authorization': f'Bearer {token}'}

report = json.loads(Path('/app/test_reports/duplicates_sweep_by_email.json').read_text())
groups = report['detalle']['mismo_email']
print(f'Grupos con mismo email: {len(groups)}')

before_active = db.candidates.count_documents({'is_deleted': {'$ne': True}})
merged, skipped = [], []

for index, group in enumerate(groups):
    batch = index // BATCH_SIZE + 1
    records = group['registros']
    primary = records[0]['id']
    secondaries = [r['id'] for r in records[1:]]

    alive = [r['id'] for r in records
             if db.candidates.find_one({'id': r['id'], 'is_deleted': {'$ne': True}}, {'_id': 0, 'id': 1})]
    if len(alive) < 2:
        skipped.append({'batch': batch, 'nombre': group['nombre'], 'motivo': 'ya_resuelto_menos_de_2_fichas_activas'})
        continue
    primary = alive[0]
    secondaries = alive[1:]

    res = requests.post(f'{API}/api/candidates/merge-multiple', headers=H, timeout=180, json={
        'primary_candidate_id': primary,
        'secondary_candidate_ids': secondaries,
        'merge_experience': True,
        'merge_education': True,
        'merge_skills': True,
        'merge_notes': True,
        'keep_all_cvs': True,
    })
    if res.status_code != 200:
        skipped.append({'batch': batch, 'nombre': group['nombre'],
                        'motivo': f'http_{res.status_code}: {res.text[:160]}'})
        print(f'  [tanda {batch}] SALTADO {group["nombre"]}: {res.status_code} {res.text[:120]}')
        continue

    data = res.json()
    merged.append({'batch': batch, 'nombre': group['nombre'], 'primary': primary,
                   'secundarias': len(secondaries), 'total_merged': data.get('total_merged')})
    print(f'  [tanda {batch}] {group["nombre"]}: {len(secondaries)} fichas fusionadas en {primary[:8]}')

after_active = db.candidates.count_documents({'is_deleted': {'$ne': True}})
result = {
    'grupos_totales': len(groups),
    'grupos_fusionados': len(merged),
    'fichas_desactivadas': sum(m['secundarias'] for m in merged),
    'candidatos_activos_antes': before_active,
    'candidatos_activos_despues': after_active,
    'saltados': skipped,
    'detalle': merged,
}
Path('/app/test_reports/email_merge_batches.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in result.items() if k != 'detalle'}, ensure_ascii=False, indent=1))
