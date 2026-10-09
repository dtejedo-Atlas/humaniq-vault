"""La actualización de CV no borra la trayectoria si el CV nuevo no trae empleos parseados."""
import os
import sys
import glob
import subprocess

import requests
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from auth import create_access_token  # noqa: E402

HOST = (sys.argv[1] if len(sys.argv) > 1 else 'https://atlas-recruiting-ai.preview.emergentagent.com').rstrip('/')
EMAIL = sys.argv[2] if len(sys.argv) > 2 else 'dtejedo@gmail.com'
CANDIDATE = sys.argv[3]
H = {'Authorization': f'Bearer {create_access_token({"sub": EMAIL})}'}

before = requests.get(f'{HOST}/api/candidates/{CANDIDATE}', headers=H, timeout=60).json()
history_before = before.get('previous_companies') or []
print('candidato:', before.get('full_name'), '| empleos antes:', len(history_before))
assert history_before, 'el candidato de prueba debe tener trayectoria previa'

env = {**os.environ, 'WITH_HISTORY': '0'}
subprocess.run([sys.executable, '/app/backend/tests/make_test_cvs.py', '/tmp/cvs_nohistory', '1'],
               capture_output=True, text=True, check=True, env=env)
path = sorted(glob.glob('/tmp/cvs_nohistory/*.pdf'))[-1]

with open(path, 'rb') as handle:
    r = requests.post(f'{HOST}/api/candidates/{CANDIDATE}/update-cv', headers=H,
                      files={'file': (os.path.basename(path), handle, 'application/pdf')}, timeout=300)
print('update-cv', r.status_code, r.text[:300])

after = requests.get(f'{HOST}/api/candidates/{CANDIDATE}', headers=H, timeout=60).json()
history_after = after.get('previous_companies') or []
print('empleos después:', len(history_after))

ok_update = r.status_code == 200
ok_history = len(history_after) >= len(history_before)
names_before = [c.get('company_name') for c in history_before]
names_after = [c.get('company_name') for c in history_after]
ok_names = all(name in names_after for name in names_before)
print(('PASS  ' if ok_update else 'FAIL  ') + 'update-cv responde 200')
print(('PASS  ' if ok_history and ok_names else 'FAIL  ') + 'trayectoria conservada tras CV sin empleos')
print('antes:', names_before)
print('después:', names_after)
sys.exit(0 if (ok_update and ok_history and ok_names) else 1)
