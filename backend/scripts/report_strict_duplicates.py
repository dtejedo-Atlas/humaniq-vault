"""Reporte SOLO LECTURA: empleos repetidos con regla estricta en fichas NO fusionadas.

Regla estricta: mismo empleador + inicio dentro de ±2 meses + fin dentro de ±2 meses
(es decir, el mismo empleo capturado dos veces). Los ascensos y puestos secuenciales no entran.

No escribe nada. Uso: python scripts/report_strict_duplicates.py
"""
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from experience_dedupe import strict_duplicates  # noqa: E402

REPORT = '/app/test_reports/strict_duplicates_report.json'


def describe(entry):
    return (f"{entry.get('title') or 'sin título'} @ {entry.get('company_name') or 'sin empresa'} "
            f"({entry.get('start_date') or '?'} → {entry.get('end_date') or 'presente'})")


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    fichas, empleos, rows = 0, 0, []

    async for c in db.candidates.find({'is_deleted': {'$ne': True}, 'last_merge_at': {'$exists': False}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'previous_companies': 1}):
        history = c.get('previous_companies') or []
        groups = strict_duplicates(history)
        if not groups:
            continue
        extra = sum(len(g) - 1 for g in groups)
        fichas += 1
        empleos += extra
        rows.append({'id': c['id'], 'nombre': c.get('full_name'), 'empleos_antes': len(history),
                     'empleos_despues': len(history) - extra,
                     'grupos': [[describe(e) for e in g] for g in groups]})

    print(f"Fichas NO fusionadas con el mismo empleo repetido (±2 meses): {fichas}")
    print(f"Empleos que se colapsarían: {empleos}\n")
    for row in rows[:10]:
        print(f"· {row['nombre']}  ({row['empleos_antes']} → {row['empleos_despues']} empleos)")
        for group in row['grupos']:
            print('    ANTES:  ' + '\n            '.join(group))
            print('    DESPUÉS: 1 registro (se conserva el más completo)')
    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump({'fichas': fichas, 'empleos': empleos, 'detalle': rows}, handle, ensure_ascii=False, indent=1)
    print(f"\nReporte completo: {REPORT}  (solo lectura, nada se escribió)")


if __name__ == '__main__':
    asyncio.run(main())
