"""company_industry con tipos inesperados no debe tumbar al candidato."""
import sys

from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from server import clean_previous_company, clean_previous_companies  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


base = {'company_name': 'Telered Comunicaciones', 'title': 'Directora Comercial'}

# Lista (caso reportado): antes lanzaba TypeError: unhashable type 'list'
entry = clean_previous_company({**base, 'company_industry': ['telecom']})
check('lista en company_industry → None', entry is not None and entry['company_industry'] is None)

# Dict
entry = clean_previous_company({**base, 'company_industry': {'key': 'telecommunications'}})
check('dict en company_industry → None', entry is not None and entry['company_industry'] is None)

# Otros tipos no hashables o inválidos
for value in (['telecommunications'], {'a': 1}, 12, None, '', 'no_existe_en_catalogo', ['a', 'b']):
    entry = clean_previous_company({**base, 'company_industry': value})
    ok = entry is not None and entry['company_industry'] is None
    check(f'valor inválido {value!r} → None', ok)

# Valor válido del catálogo se conserva
entry = clean_previous_company({**base, 'company_industry': 'telecommunications'})
check('valor del catálogo se conserva', entry['company_industry'] == 'telecommunications', str(entry['company_industry']))

# Lista completa: el empleo malo no tumba al candidato ni elimina los buenos
history = clean_previous_companies([
    {**base, 'company_industry': ['telecom']},
    {'company_name': 'Grupo Nortec', 'title': 'Gerente', 'company_industry': 'manufacturing'},
    'cadena suelta en vez de objeto',
    {'company_industry': ['x']},  # sin empresa ni título → se descarta
    {'company_name': 'Banco Centinela', 'title': 'Ejecutiva', 'company_caliber': ['pyme']},
])
names = [c['company_name'] for c in history]
check('lista mixta conserva los empleos válidos',
      names == ['Telered Comunicaciones', 'Grupo Nortec', 'Banco Centinela'], str(names))
check('industria válida intacta en lista mixta', history[1]['company_industry'] == 'manufacturing')
check('caliber con tipo inválido → None', history[2]['company_caliber'] is None)

print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
