"""Corrige los años de experiencia de las fichas que bajaron tras la deduplicación.

Regla: años = (inicio del primer empleo, sin prácticas/becario → fin del último empleo u hoy)
       − huecos sin empleo de 12 meses o más.  Nunca más que ese lapso.

- Guarda el valor previo en `years_experience_pre_fix` (el original de antes del dedupe ya vive
  en `years_experience_pre_dedupe` y no se sobrescribe).
- Si la ficha no tiene fechas utilizables, no se toca.
- Sin `--apply` solo muestra la tabla (no escribe nada).

Uso: python tests/fix_experience_years.py [--apply]
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from experience_dedupe import experience_years_from_history  # noqa: E402
from industry_trajectory import total_experience_years  # noqa: E402

APPLY = '--apply' in sys.argv
REPORT = '/app/test_reports/fix_experience_years.json'


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    targets, skipped = [], []

    async for c in db.candidates.find({'years_experience_pre_dedupe': {'$exists': True},
                                       'is_deleted': {'$ne': True}}, {'_id': 0}):
        before, original = c.get('years_experience'), c.get('years_experience_pre_dedupe')
        if not (isinstance(before, (int, float)) and isinstance(original, (int, float)) and before < original):
            continue
        history = c.get('previous_companies') or []
        nuevo = experience_years_from_history(history)
        union = total_experience_years({**c, 'previous_companies': history})
        if nuevo is None:
            skipped.append({'nombre': c.get('full_name'), 'motivo': 'sin fechas utilizables'})
            continue
        targets.append({'id': c['id'], 'nombre': c.get('full_name'), 'anterior': before,
                        'original_pre_dedupe': original,
                        'union_periodos': None if union is None else round(union), 'nuevo': nuevo})

    width = max((len(t['nombre'] or '') for t in targets), default=10) + 2
    print(f"Fichas a corregir: {len(targets)}  ({'APLICANDO' if APPLY else 'SIMULACIÓN'})\n")
    print('CANDIDATO'.ljust(width) + 'ANTERIOR'.ljust(10) + 'UNIÓN'.ljust(8) + 'NUEVO')
    print('-' * (width + 26))
    for t in targets:
        print((t['nombre'] or '').ljust(width) + str(t['anterior']).ljust(10)
              + str(t['union_periodos']).ljust(8) + str(t['nuevo']))
    for s in skipped:
        print(f"(sin cambio) {s['nombre']}: {s['motivo']}")

    # Conteo SOLO LECTURA del resto de la base con la misma regla
    cambios_grandes, revisados = 0, 0
    async for c in db.candidates.find({'is_deleted': {'$ne': True}},
                                      {'_id': 0, 'id': 1, 'years_experience': 1, 'previous_companies': 1}):
        if c['id'] in [t['id'] for t in targets]:
            continue
        actual = c.get('years_experience')
        nuevo = experience_years_from_history(c.get('previous_companies') or [])
        if isinstance(actual, (int, float)) and nuevo is not None:
            revisados += 1
            if abs(nuevo - actual) > 2:
                cambios_grandes += 1
    print(f"\nResto de la base (solo conteo, no se toca): {cambios_grandes} de {revisados} fichas "
          f"cambiarían más de 2 años con esta regla.")

    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump({'aplicado': APPLY, 'fichas': targets, 'omitidas': skipped,
                   'resto_base_cambios_mayores_2_anios': cambios_grandes, 'resto_base_revisadas': revisados},
                  handle, ensure_ascii=False, indent=1)
    print(f"Reporte: {REPORT}")

    if not APPLY:
        print('\nNada se escribió. Corre con --apply para guardar.')
        return

    for t in targets:
        await db.candidates.update_one({'id': t['id']}, {'$set': {
            'years_experience': t['nuevo'],
            'years_experience_pre_fix': t['anterior'],
            'years_experience_fix_at': stamp,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }})
    print(f"\nAños corregidos en {len(targets)} fichas (reversible con years_experience_pre_fix).")


asyncio.run(main())
