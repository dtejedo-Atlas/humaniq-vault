"""Deduplicación de experiencia laboral en fusiones de fichas."""
import sys

sys.path.insert(0, '/app/backend')
from experience_dedupe import (  # noqa: E402
    dedupe_experience, experience_years_from_history, is_same_job, normalize_company, strict_duplicates,
)

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

# Agrupamiento transitivo e independiente del orden (caso Humberto: registro "paraguas" 2005-2019)
coca = [
    {'company_name': 'Coca-Cola FEMSA', 'title': 'Planeación de Supply Chain', 'start_date': '2015-01', 'end_date': '2016-01'},
    {'company_name': 'Coca-Cola FEMSA', 'title': 'Especialista Distribución', 'start_date': '2011-01', 'end_date': '2013-01'},
    {'company_name': 'Coca-Cola FEMSA', 'title': 'Facilitador Almacén', 'start_date': '2009-01', 'end_date': '2011-01'},
    {'company_name': 'Coca-Cola FEMSA', 'title': 'Distribution & Transportation Lead', 'start_date': '2005-11',
     'end_date': '2019-06', 'description': 'responsable de distribución nacional'},
    {'company_name': 'Otra Empresa', 'title': 'Gerente', 'start_date': '2020-01', 'end_date': None},
]
coca_kept = dedupe_experience(coca)
check('el registro paraguas colapsa todos los puestos de la misma empresa',
      len(coca_kept) == 2, str([k['title'] for k in coca_kept]))
check('el registro colapsado toma el título más reciente',
      any(k['title'] == 'Planeación de Supply Chain' for k in coca_kept),
      str([k['title'] for k in coca_kept]))
coca_merged = [k for k in coca_kept if k['company_name'] == 'Coca-Cola FEMSA'][0]
check('la descripción conserva la trayectoria interna con fechas',
      'Roles:' in coca_merged['description']
      and 'Distribution & Transportation Lead 2005–2019' in coca_merged['description']
      and 'Facilitador Almacén 2009–2011' in coca_merged['description'],
      coca_merged['description'])
check('no se pierde ningún título al colapsar',
      all(t in coca_merged['description'] or t == coca_merged['title']
          for t in ['Planeación de Supply Chain', 'Especialista Distribución', 'Facilitador Almacén',
                    'Distribution & Transportation Lead']))
check('el resultado no depende del orden del historial',
      len(dedupe_experience(list(reversed(coca)))) == len(coca_kept))
check('no toca empleos de otra empresa',
      any(k['company_name'] == 'Otra Empresa' for k in coca_kept))

# OBLIGATORIO: puestos secuenciales con fechas de solo año (caso Luis De la Llata en Movistar)
movistar = [
    {'company_name': 'Movistar', 'title': 'Gerente de Ventas', 'start_date': '2014', 'end_date': '2018'},
    {'company_name': 'Movistar', 'title': 'Director Comercial', 'start_date': '2018', 'end_date': '2021'},
]
check('puestos secuenciales con fechas de solo año NUNCA colapsan',
      len(dedupe_experience(movistar)) == 2 and not is_same_job(*movistar))
check('tres puestos secuenciales por año se conservan',
      len(dedupe_experience(movistar + [{'company_name': 'Movistar', 'title': 'Subdirector',
                                         'start_date': '2021', 'end_date': '2024'}])) == 3)

# Regla estricta: el mismo empleo listado dos veces (±2 meses)
strict = [
    {'company_name': 'Telcel', 'title': 'Director Comercial', 'start_date': '2015-01', 'end_date': '2019-03'},
    {'company_name': 'Telcel S.A. de C.V.', 'title': 'Director comercial', 'start_date': '2015-02', 'end_date': '2019-04'},
    {'company_name': 'Telcel', 'title': 'Gerente', 'start_date': '2010-01', 'end_date': '2014-12'},
]
check('la regla estricta detecta el empleo repetido',
      len(strict_duplicates(strict)) == 1 and len(strict_duplicates(strict)[0]) == 2)
check('la regla estricta no toca puestos secuenciales por año', strict_duplicates(movistar) == [])
check('la regla estricta no colapsa el paraguas de Coca-Cola', strict_duplicates(coca) == [])

# Años de experiencia: lapso del primer empleo al último menos huecos de 12+ meses
hist = [
    {'company_name': 'A', 'title': 'Practicante', 'start_date': '2000-01', 'end_date': '2001-01'},
    {'company_name': 'B', 'title': 'Analista', 'start_date': '2005-01', 'end_date': '2010-01'},
    {'company_name': 'C', 'title': 'Gerente', 'start_date': '2012-01', 'end_date': '2020-01'},
]
hoy = 2026 * 12 + 1
check('los años excluyen prácticas y huecos de 12+ meses',
      experience_years_from_history(hist, hoy) == 13, str(experience_years_from_history(hist, hoy)))
check('los empleos duplicados no inflan los años',
      experience_years_from_history(hist + [dict(hist[1])], hoy) == 13)
check('empleo abierto cuenta hasta hoy',
      experience_years_from_history([{'company_name': 'A', 'title': 'Director', 'start_date': '2016-01',
                                      'end_date': None}], hoy) == 10)
check('sin fechas no hay valor de años',
      experience_years_from_history([{'company_name': 'A', 'title': 'Director'}], hoy) is None)

print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
