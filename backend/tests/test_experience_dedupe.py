"""Deduplicación de experiencia laboral en fusiones de fichas."""
import sys

sys.path.insert(0, '/app/backend')
from experience_dedupe import dedupe_experience, is_same_job, normalize_company  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


# Normalización de razón social
check('normaliza sufijos y acentos', normalize_company('INDALUM S.A. de C.V.') == 'indalum',
      normalize_company('INDALUM S.A. de C.V.'))
check('quita sufijo Smiths', normalize_company('John Crane Smiths') == 'john crane',
      normalize_company('John Crane Smiths'))
check('quita México', normalize_company('Lenovo Global Technology México') == 'lenovo global technology',
      normalize_company('Lenovo Global Technology México'))

# Mismo empleo: nombre contenido + mismo periodo
a = {'company_name': 'John Crane Smiths', 'title': 'Director', 'start_date': '2011-10', 'end_date': '2025-10'}
b = {'company_name': 'John Crane', 'title': 'Managing Director Oil & Gas', 'start_date': '2011-10', 'end_date': '2025-10',
     'description': 'Responsable de la división de energía'}
check('empresa contenida + mismo periodo = mismo empleo', is_same_job(a, b))

# Ascenso en la misma empresa con periodos contiguos: NO es el mismo empleo
c = {'company_name': 'ECISA', 'title': 'Subgerente de Ventas', 'start_date': '2019-10', 'end_date': '2020-08'}
d = {'company_name': 'ECISA', 'title': 'Ejecutiva de Ventas', 'start_date': '2018-10', 'end_date': '2019-10'}
check('ascenso con periodos contiguos se conserva aparte', not is_same_job(c, d))

# Empresas distintas en el mismo periodo
e = {'company_name': 'Siemens', 'title': 'Project Manager', 'start_date': '1996-05', 'end_date': '2002-12'}
f = {'company_name': 'Proleit', 'title': 'General Manager', 'start_date': '1996-05', 'end_date': '2002-12'}
check('empresas distintas no se fusionan', not is_same_job(e, f))

# Deduplicación completa estilo Matthias
history = [a, b, c, d, e,
           {'company_name': 'Siemens AG', 'title': 'Gerente de Control', 'start_date': '2007-10', 'end_date': '2009-05'},
           {'company_name': 'Siemens', 'title': 'Power Generation Manager', 'start_date': '2007-10', 'end_date': '2009-05'},
           {'company_name': 'Siemens', 'title': 'Project Management', 'start_date': '1996-05', 'end_date': '2002-12'}]
kept = dedupe_experience(history)
names = [(k['company_name'], k['start_date']) for k in kept]
check('historial con duplicados queda en 5 empleos', len(kept) == 5, str(names))
check('conserva el registro más completo', any(k.get('description') for k in kept if k['start_date'] == '2011-10'))
check('conserva los dos periodos distintos de ECISA',
      sum(1 for k in kept if k['company_name'] == 'ECISA') == 2)
check('conserva los dos periodos distintos de Siemens',
      sum(1 for k in kept if 'siemens' in normalize_company(k['company_name'])) == 2)
check('orden descendente por fecha de inicio',
      [k['start_date'] for k in kept] == sorted([k['start_date'] for k in kept], reverse=True))

# Entradas basura no truenan
check('entradas no-dict se ignoran', len(dedupe_experience(['texto', None, a])) == 1)
check('lista vacía', dedupe_experience([]) == [])

# Fechas ausentes: misma empresa cuenta como el mismo empleo
g = {'company_name': 'Acme', 'title': 'Gerente'}
h = {'company_name': 'Acme', 'title': 'Gerente comercial', 'description': 'más completo'}
check('sin fechas, misma empresa se fusiona', len(dedupe_experience([g, h])) == 1)

print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
