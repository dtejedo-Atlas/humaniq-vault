"""Limpieza de empleos duplicados en fichas fusionadas (reversible).

- Respaldo completo de cada ficha afectada: colección `experience_dedupe_backups` + archivo JSON.
- El historial original se guarda en `previous_companies_pre_dedupe` (y los años en `years_experience_pre_dedupe`).
- Al colapsar se conserva la trayectoria: título del puesto más reciente + "Roles: …" en la descripción.
- Los años se recalculan como lapso del primer al último empleo menos huecos de 12+ meses.
- Sin `--apply` solo muestra el reporte (no escribe nada).

Uso: python scripts/dedupe_merged_experience.py [--apply] [--only "Nombre"]
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
from experience_dedupe import dedupe_experience, experience_years_from_history  # noqa: E402
from industry_trajectory import total_experience_years  # noqa: E402

APPLY = '--apply' in sys.argv
ONLY = sys.argv[sys.argv.index('--only') + 1].lower() if '--only' in sys.argv else None
BACKUP_DIR = '/app/memory/backups'


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    affected, backups = [], []

    async for c in db.candidates.find({'last_merge_at': {'$exists': True}, 'is_deleted': {'$ne': True}}, {'_id': 0}):
        if ONLY and ONLY not in (c.get('full_name') or '').lower():
            continue
        history = c.get('previous_companies') or []
        kept = dedupe_experience(history)
        if len(kept) >= len(history):
            continue
        years_before = c.get('years_experience')
        years_after = experience_years_from_history(kept)
        years_union = total_experience_years({**c, 'previous_companies': kept})
        affected.append((c, history, kept, years_before, years_after, years_union))
        backups.append(c)

    print(f"Fichas fusionadas con empleos duplicados: {len(affected)}  ({'APLICANDO' if APPLY else 'SIMULACIÓN'})")
    width = max((len(c.get('full_name') or '') for c, *_ in affected), default=10) + 2
    print('\n' + 'CANDIDATO'.ljust(width) + 'EMPLEOS'.ljust(16) + 'AÑOS (actual → unión → nuevo)')
    print('-' * (width + 48))
    for c, history, kept, yb, ya, yu in affected:
        years = f"{yb if yb is not None else '—'} → {yu if yu is None else round(yu)} → " \
                f"{ya if ya is not None else 'sin fechas (se conserva)'}"
        print((c.get('full_name') or '').ljust(width) + f"{len(history)} → {len(kept)}".ljust(16) + years)

    if not APPLY:
        print('\nNada se escribió. Corre con --apply para ejecutar la limpieza.')
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f'experience_dedupe_{stamp}.json')
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(backups, handle, ensure_ascii=False, default=str, indent=1)
    await db.experience_dedupe_backups.insert_one({'stamp': stamp, 'count': len(backups), 'candidates': backups})
    print(f'\nRespaldo: {path} y colección experience_dedupe_backups (stamp {stamp})')

    for c, history, kept, yb, ya, yu in affected:
        update = {'previous_companies': kept, 'updated_at': datetime.now(timezone.utc).isoformat(),
                  'experience_dedupe_at': stamp}
        if 'previous_companies_pre_dedupe' not in c:
            update['previous_companies_pre_dedupe'] = history
            update['years_experience_pre_dedupe'] = yb
        if ya is not None:
            update['years_experience'] = int(ya)
        await db.candidates.update_one({'id': c['id']}, {'$set': update})
    print(f'Limpieza aplicada a {len(affected)} fichas (reversible con previous_companies_pre_dedupe).')


if __name__ == '__main__':
    asyncio.run(main())
