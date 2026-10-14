"""Alerta de estabilidad con los 8 candidatos reales indicados por el usuario."""
import asyncio
import os
import sys
from datetime import date

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from stability_alert import compute_stability_alert  # noqa: E402

TODAY = date.today()
EXPECTED = {
    'Edgar Ochoa': {'level': 'rojo', 'e5': 4, 'e10': 5},
    'Jesús A. Oliden González': {'level': 'rojo', 'e5': 4, 'short': 'HP'},
    'Miguel Angel Olvera Cadena': {'level': 'rojo', 'e5': 4, 'parallel': 'Interlinked'},
    'Jose del Moral Morones': {'level': 'amarillo', 'e5': 3, 'sin_actual': True},
    'Francisco Somohano Mendez': {'level': 'amarillo', 'e5': 3},
    'Rodrigo Hevia Coto': {'level': 'verde', 'parallel_many': ['Alibaba', 'Billpocket']},
    'Luis De la Llata': {'level': 'verde', 'e5': 1},
    'Alexander Leigh': {'level': 'verde', 'gap': 12},
}
results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    print(f'Hoy: {TODAY.isoformat()}\n')
    print(f"{'CANDIDATO':30}{'NIVEL':11}{'5A':>3}{'10A':>4}  TEXTO / SEÑALES")
    print('-' * 118)
    for full_name, exp in EXPECTED.items():
        c = await db.candidates.find_one({'full_name': full_name, 'is_deleted': {'$ne': True}}, {'_id': 0})
        if not c:
            check(f'{full_name} existe en la base', False)
            continue
        a = compute_stability_alert(c, TODAY)
        señales = []
        if a['roles_paralelos']:
            señales.append('paralelos: ' + ', '.join(p['empleador'][:22] for p in a['roles_paralelos']))
        if a['estancias_cortas']:
            señales.append('cortas: ' + ', '.join(f"{s['empleador'][:14]} {s['meses']}m" for s in a['estancias_cortas']))
        if a['huecos']:
            señales.append('huecos: ' + ', '.join(f"{g['meses']}m" for g in a['huecos']))
        if a['sin_empleo_actual']:
            señales.append('sin empleo actual')
        print(f"{full_name[:29]:30}{a['level']:11}{a['employers_5y']:>3}{a['employers_10y']:>4}  {a['texto']} · " +
              ' · '.join(señales))

        check(f'{full_name}: nivel {exp["level"]}', a['level'] == exp['level'], a['level'])
        if 'e5' in exp:
            check(f'{full_name}: {exp["e5"]} empleadores en 5 años', a['employers_5y'] == exp['e5'], str(a['employers_5y']))
        if 'e10' in exp:
            check(f'{full_name}: {exp["e10"]} empleadores en 10 años', a['employers_10y'] == exp['e10'], str(a['employers_10y']))
        if 'short' in exp:
            check(f'{full_name}: {exp["short"]} en estancias cortas',
                  any(exp['short'].lower() in s['empleador'].lower() for s in a['estancias_cortas']),
                  str(a['estancias_cortas']))
        if 'parallel' in exp:
            check(f'{full_name}: {exp["parallel"]} en roles paralelos',
                  any(exp['parallel'].lower() in p['empleador'].lower() for p in a['roles_paralelos']),
                  str([p['empleador'] for p in a['roles_paralelos']]))
        if 'parallel_many' in exp:
            for needle in exp['parallel_many']:
                check(f'{full_name}: {needle} en roles paralelos',
                      any(needle.lower() in p['empleador'].lower() for p in a['roles_paralelos']),
                      str([p['empleador'] for p in a['roles_paralelos']]))
        if exp.get('sin_actual'):
            check(f'{full_name}: sin_empleo_actual', a['sin_empleo_actual'] is True)
        if 'gap' in exp:
            check(f'{full_name}: hueco de ~{exp["gap"]} meses',
                  any(abs(g['meses'] - exp['gap']) <= 2 for g in a['huecos']), str(a['huecos']))

    # Un mismo empleador con dos periodos cuenta una vez
    edgar = await db.candidates.find_one({'full_name': 'Edgar Ochoa'}, {'_id': 0})
    alert = compute_stability_alert(edgar, TODAY)
    redline = [t for t in alert['timeline'] if 'redline' in t['empleador'].lower()]
    check('Redline/Aviat aparece dos veces en el timeline pero cuenta como un empleador', len(redline) == 2)

    print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
    return 0 if all(ok for _, ok in results) else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
