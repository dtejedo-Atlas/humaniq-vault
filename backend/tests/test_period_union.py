"""Años por UNIÓN de periodos: dos empleos simultáneos no cuentan doble."""
import sys
from datetime import datetime

sys.path.insert(0, '/app/backend')
from industry_trajectory import (industry_affinity, merge_periods, total_experience_years,  # noqa: E402
                                 trajectory_profile, union_years, weighted_union_years)

NOW = datetime(2026, 1, 1)
results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


d = datetime
check('une periodos traslapados',
      merge_periods([(d(2020, 1, 1), d(2022, 1, 1)), (d(2021, 1, 1), d(2023, 1, 1))]) == [(d(2020, 1, 1), d(2023, 1, 1))])
check('conserva periodos separados',
      len(merge_periods([(d(2010, 1, 1), d(2012, 1, 1)), (d(2015, 1, 1), d(2016, 1, 1))])) == 2)
check('traslape total cuenta una vez',
      round(union_years([(d(2020, 1, 1), d(2024, 1, 1)), (d(2020, 1, 1), d(2024, 1, 1))]), 1) == 4.0,
      str(round(union_years([(d(2020, 1, 1), d(2024, 1, 1)), (d(2020, 1, 1), d(2024, 1, 1))]), 1)))
check('ponderado por recencia no duplica traslapes',
      round(weighted_union_years([(d(2020, 1, 1), d(2024, 1, 1)), (d(2021, 1, 1), d(2024, 1, 1))], NOW), 1)
      == round(weighted_union_years([(d(2020, 1, 1), d(2024, 1, 1))], NOW), 1))

# Dos empleos simultáneos en la misma ficha
simultaneo = {'full_name': 'Simultánea', 'industry': 'telecommunications', 'previous_companies': [
    {'company_name': 'Telecom A', 'company_industry': 'telecommunications', 'start_date': '2018-01', 'end_date': '2024-01'},
    {'company_name': 'Consultora B', 'company_industry': 'telecommunications', 'start_date': '2019-01', 'end_date': '2023-01'},
]}
check('años de experiencia por unión (6, no 10)', total_experience_years(simultaneo, NOW) == 6.0,
      str(total_experience_years(simultaneo, NOW)))

xi, ci, ev = industry_affinity(simultaneo, {'job_scorecard': {'target_industries': ['telecommunications'],
                                                              'industry_requirement': 'obligatoria'}}, NOW)
check('años en industria objetivo por unión (6, no 10)', ev['target_years'] == 6.0, str(ev['target_years']))
check('proporción 100% con toda la trayectoria en la industria objetivo', ev['proportion_weighted'] == 1.0,
      str(ev['proportion_weighted']))

# Periodos separados sí suman
separado = {'full_name': 'Separada', 'industry': 'telecommunications', 'previous_companies': [
    {'company_name': 'Telecom A', 'company_industry': 'telecommunications', 'start_date': '2017-01', 'end_date': '2020-01'},
    {'company_name': 'Retail B', 'company_industry': 'retail', 'start_date': '2021-01', 'end_date': '2024-01'},
]}
check('periodos separados suman (6 años)', total_experience_years(separado, NOW) == 6.0,
      str(total_experience_years(separado, NOW)))
xi2, ci2, ev2 = industry_affinity(separado, {'job_scorecard': {'target_industries': ['telecommunications'],
                                                               'industry_requirement': 'preferente'}}, NOW)
check('solo cuenta el periodo de la industria objetivo', ev2['target_years'] == 3.0, str(ev2['target_years']))
check('proporción menor a 1 con industrias mezcladas', 0 < ev2['proportion_weighted'] < 1,
      str(ev2['proportion_weighted']))

# Sin fechas no inventa años
sin_fechas = {'full_name': 'Sin fechas', 'previous_companies': [{'company_name': 'Acme'}]}
check('sin fechas no calcula años', total_experience_years(sin_fechas, NOW) is None)

# El perfil de trayectoria sigue exponiendo los años por empleo
rows = trajectory_profile(simultaneo, NOW)
check('trayectoria conserva un renglón por empleo', len(rows) == 2 and all(r['years'] > 0 for r in rows))

print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
