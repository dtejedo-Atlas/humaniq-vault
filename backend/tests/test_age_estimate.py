"""Edad estimada: casos obligatorios + tabla del shortlist de Director Comercial (Diri)."""
import asyncio
import os
import sys
from datetime import date

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from age_estimate import AGE_NOTICE_CAREER_YEARS, estimate_age  # noqa: E402

TODAY = date.today()
JOB_ID = 'a5a9ceb5-6a43-4547-bd30-7966a96959b5'
results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


# 1. Primer empleo en 1997
a = estimate_age({'previous_companies': [{'company_name': 'Telefónica', 'title': 'Gerente', 'start_date': '1997-08'},
                                         {'company_name': 'HCL', 'title': 'Director', 'start_date': '2024-11'}]}, TODAY)
esperado = (TODAY.year - 1997) + 22
check('primer empleo 1997 dispara notificación', a['notificacion'] is True, str(a))
check(f'rango {esperado - 3}–{esperado + 3}', (a['rango_min'], a['rango_max']) == (esperado - 3, esperado + 3),
      f"{a['rango_min']}–{a['rango_max']}")
check('fuente primer_empleo', a['fuente'] == 'primer_empleo' and '1997' in a['detalle'], a['detalle'])

# 2. Frontera: exactamente 25 años de carrera y edad estimada < 50
borde_year = TODAY.year - AGE_NOTICE_CAREER_YEARS
b = estimate_age({'previous_companies': [{'company_name': 'Acme', 'title': 'Gerente', 'start_date': f'{borde_year}-01'}]},
                 TODAY)
check('25 años exactos de carrera no notifica', b['notificacion'] is False, str(b))
check('25 años exactos: edad estimada 47 y años_carrera 25',
      b['edad_estimada'] == 47 and b['años_carrera'] == 25, f"{b['edad_estimada']}/{b['años_carrera']}")

# 3. Primer empleo 1996 con huecos que suman 8 años: usa el lapso, no la suma
c = estimate_age({'previous_companies': [
    {'company_name': 'Uno', 'title': 'Analista', 'start_date': '1996-01', 'end_date': '2004-01'},
    {'company_name': 'Dos', 'title': 'Gerente', 'start_date': '2012-01', 'end_date': '2020-01'},
    {'company_name': 'Tres', 'title': 'Director', 'start_date': '2024-01'},
]}, TODAY)
check('usa el lapso desde 1996, no la suma de periodos',
      c['edad_estimada'] == (TODAY.year - 1996) + 22 and c['años_carrera'] == TODAY.year - 1996, str(c))

# 4. Sin fechas y years_experience = 15
d = estimate_age({'years_experience': 15, 'previous_companies': [{'company_name': 'Acme', 'title': 'Gerente'}]}, TODAY)
check('sin fechas usa years_experience con confianza baja',
      d['fuente'] == 'years_experience' and d['confianza'] == 'baja' and d['edad_estimada'] == 37, str(d))
check('sin fechas y 15 años no notifica', d['notificacion'] is False)

# 5. Prácticas/becario se ignoran para el primer empleo
e = estimate_age({'previous_companies': [{'company_name': 'Uno', 'title': 'Becario', 'start_date': '1990-01'},
                                         {'company_name': 'Dos', 'title': 'Analista', 'start_date': '2000-01'}]}, TODAY)
check('ignora puestos de becario/prácticas', '2000' in e['detalle'], e['detalle'])

# 6. Edad explícita manda y es de confianza alta
f = estimate_age({'age': 45, 'previous_companies': [{'company_name': 'X', 'title': 'Y', 'start_date': '1990-01'}]}, TODAY)
check('edad declarada tiene prioridad y confianza alta',
      f['fuente'] == 'nacimiento' and f['confianza'] == 'alta' and f['rango_min'] == f['rango_max'] == 45, str(f))

# 7. Año de egreso de licenciatura
g = estimate_age({'education': [{'degree': 'Licenciatura en Administración', 'institution': 'UNAM',
                                 'graduation_year': 2008}]}, TODAY)
check('egreso de licenciatura con rango ±2 y confianza media',
      g['fuente'] == 'egreso' and g['edad_estimada'] == (TODAY.year - 2008) + 23
      and (g['rango_max'] - g['rango_min']) == 4, str(g))

# 8. Sin ningún dato
h = estimate_age({'full_name': 'Sin datos'}, TODAY)
check('sin datos no estima ni notifica', h['edad_estimada'] is None and h['notificacion'] is False, str(h))


async def tabla():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    snap = await db.job_match_snapshots.find_one({'job_id': JOB_ID, 'engine': 'unified'}, {'_id': 0})
    rows = ((snap or {}).get('payload') or {}).get('results') or []
    ids, seen = [], set()
    for r in rows:
        if r['candidate_id'] not in seen:
            seen.add(r['candidate_id'])
            ids.append(r['candidate_id'])
        if len(ids) >= 19:
            break
    print(f'\nTabla de edad estimada — shortlist Director Comercial (Diri), hoy {TODAY.isoformat()}')
    print(f"{'CANDIDATO':32}{'EDAD':>5}{'RANGO':>9}  {'FUENTE':16}{'CONF':7}{'CARRERA':>8}  NOTIF  DETALLE")
    print('-' * 132)
    for cid in ids:
        c = await db.candidates.find_one({'id': cid}, {'_id': 0})
        if not c:
            continue
        a = estimate_age(c, TODAY)
        rango = f"{a['rango_min']}–{a['rango_max']}" if a['edad_estimada'] is not None else '—'
        print(f"{(c.get('full_name') or '')[:31]:32}{str(a['edad_estimada'] or '—'):>5}{rango:>9}  "
              f"{str(a['fuente'] or '—'):16}{str(a['confianza'] or '—'):7}{str(a['años_carrera'] or '—'):>8}  "
              f"{'SÍ' if a['notificacion'] else 'no':5}  {(a['detalle'] or '')[:52]}")


asyncio.run(tabla())
print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
