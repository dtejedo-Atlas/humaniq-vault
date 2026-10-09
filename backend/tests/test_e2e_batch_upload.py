"""E2E de carga por lotes: lote de 3, segundo lote inmediato y recuperación tipo recarga.

Corre contra el host indicado con la cuenta indicada (token firmado localmente).
Uso: python tests/test_e2e_batch_upload.py [host] [email]
"""
import os
import sys
import time
import glob
import subprocess

import requests
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from auth import create_access_token  # noqa: E402

HOST = (sys.argv[1] if len(sys.argv) > 1 else 'https://atlas-recruiting-ai.preview.emergentagent.com').rstrip('/')
EMAIL = sys.argv[2] if len(sys.argv) > 2 else 'dtejedo@gmail.com'
H = {'Authorization': f'Bearer {create_access_token({"sub": EMAIL})}'}
results = []


def record(name, ok, extra=''):
    results.append((name, ok, extra))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


def make_cvs(count):
    out = subprocess.run([sys.executable, '/app/backend/tests/make_test_cvs.py', '/tmp/cvs_e2e', str(count)],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()


def post_batch(paths):
    files = [('files', (os.path.basename(p), open(p, 'rb'), 'application/pdf')) for p in paths]
    return requests.post(f'{HOST}/api/candidates/upload-batch', headers=H, files=files, timeout=300)


def poll(batch_id, tries=60, delay=8):
    last = None
    for _ in range(tries):
        r = requests.get(f'{HOST}/api/candidates/batch/{batch_id}', headers=H, timeout=60)
        if r.status_code != 200:
            return r.status_code, None
        last = r.json()
        if last['is_complete']:
            return 200, last
        time.sleep(delay)
    return 200, last


# Caso 1: lote de 3 CVs
first = post_batch(make_cvs(3))
record('POST lote 1 devuelve 200', first.status_code == 200, f'status={first.status_code} {first.text[:160]}')
if first.status_code != 200:
    sys.exit(1)
batch1 = first.json()['batch_id']
record('lote 1 encola 3 archivos', first.json()['queued'] == 3, str(first.json()['queued']))

# Caso 3 (recarga a la mitad): mientras el lote 1 corre, se consulta como lo haría una página recargada
mid = requests.get(f'{HOST}/api/candidates/batch/{batch1}', headers=H, timeout=60)
latest = requests.get(f'{HOST}/api/candidates/upload-batches/latest', headers=H, timeout=60)
record('GET estado a mitad de proceso devuelve 200', mid.status_code == 200, f'status={mid.status_code}')
record('GET último lote recupera el lote en curso',
       latest.status_code == 200 and latest.json().get('batch_id') == batch1, latest.text[:120])

# Caso 2: segundo lote inmediato (sin esperar a que termine el primero)
second = post_batch(make_cvs(3))
record('POST lote 2 inmediato devuelve 200', second.status_code == 200, f'status={second.status_code} {second.text[:200]}')
batch2 = second.json()['batch_id'] if second.status_code == 200 else None

code1, status1 = poll(batch1)
ok1 = code1 == 200 and status1 and status1['is_complete']
record('lote 1 termina sin 403/404', bool(ok1), f'code={code1} stats={status1 and status1["stats"]}')

if batch2:
    code2, status2 = poll(batch2)
    ok2 = code2 == 200 and status2 and status2['is_complete']
    record('lote 2 termina sin 403/404', bool(ok2), f'code={code2} stats={status2 and status2["stats"]}')

# Caso 4: un lote inexistente devuelve 404 (el frontend limpia el seguimiento con eso)
ghost = requests.get(f'{HOST}/api/candidates/batch/00000000-0000-0000-0000-000000000000', headers=H, timeout=60)
record('lote inexistente devuelve 404', ghost.status_code == 404, f'status={ghost.status_code}')

# Caso 5: tras terminar, la cuota queda libre (un tercer lote entra sin 429)
third = post_batch(make_cvs(1))
record('tercer lote sin 429 tras liberar cuota', third.status_code == 200, f'status={third.status_code} {third.text[:200]}')
if third.status_code == 200:
    poll(third.json()['batch_id'])

print('\nTOTAL', sum(1 for _, ok, _ in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
