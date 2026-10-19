"""Dominio propio: CORS, enlaces de correo y duración de la invitación.

Sin red ni base de datos. Uso: python tests/test_public_domain_links.py
"""
import os
import sys

sys.path.insert(0, '/app/backend')
import cors_config  # noqa: E402
import invitation_service  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


DOMINIO = 'https://vault.humaniq.com.mx'

# --- CORS ---
os.environ['HUMANIQ_CORS_ORIGINS'] = 'https://atlas-recruiting-ai.emergent.host'
origins = cors_config.get_cors_origins()
check('el dominio propio siempre queda permitido aunque falte en la configuración',
      DOMINIO in origins, ', '.join(origins))
check('no se cuela ningún comodín', all('*' not in o for o in origins))

os.environ['HUMANIQ_CORS_ORIGINS'] = ''
os.environ['CORS_ORIGINS'] = '*'
check('con CORS_ORIGINS en comodín, el respaldo incluye el dominio propio',
      DOMINIO in cors_config.get_cors_origins())

os.environ['HUMANIQ_CORS_ORIGINS'] = f'{DOMINIO},https://atlas-recruiting-ai.emergent.host'
check('sin duplicados cuando sí está configurado',
      cors_config.get_cors_origins().count(DOMINIO) == 1, str(cors_config.get_cors_origins()))

# --- Enlaces de correo ---
os.environ['PUBLIC_APP_URL'] = DOMINIO
sys.modules.pop('server', None)
from server import public_app_url  # noqa: E402

check('los enlaces usan el dominio propio aunque el frontend mande otro origen',
      public_app_url('https://atlas-recruiting-ai.preview.emergentagent.com') == DOMINIO)
check('los enlaces usan el dominio propio sin origen', public_app_url(None) == DOMINIO)
check('se ignora una barra final', public_app_url(DOMINIO + '/') == DOMINIO)

del os.environ['PUBLIC_APP_URL']
check('sin PUBLIC_APP_URL se acepta solo un origen autorizado',
      public_app_url('https://atlas-recruiting-ai.emergent.host') == 'https://atlas-recruiting-ai.emergent.host')
check('sin PUBLIC_APP_URL se rechaza un origen desconocido',
      public_app_url('https://malicioso.example.com') in cors_config.get_cors_origins())

# --- Duración de los tokens ---
check('la invitación dura 7 días', invitation_service.ttl_hours('invitation') == 168,
      str(invitation_service.ttl_hours('invitation')))
check('el restablecimiento sigue siendo corto', invitation_service.ttl_hours('reset') == 48)

if __name__ == '__main__':
    print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
    sys.exit(0 if all(ok for _, ok in results) else 1)
