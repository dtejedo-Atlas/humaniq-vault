"""Auditoría de empleos duplicados en fichas fusionadas (solo lectura).

Regla propuesta: mismo empleo = empresa normalizada similar (una contiene a la otra, sin acentos
ni sufijos de razón social) + periodos que se traslapan. Se conserva el registro más completo.
"""
import asyncio
import os
import re
import sys
import unicodedata

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from experience_dedupe import dedupe_experience, normalize_company  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else None


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    query = {'last_merge_at': {'$exists': True}, 'is_deleted': {'$ne': True}}
    total, affected = 0, []
    async for c in db.candidates.find(query, {'_id': 0, 'id': 1, 'full_name': 1, 'previous_companies': 1, 'last_merge_at': 1}):
        total += 1
        history = c.get('previous_companies') or []
        kept = dedupe_experience(history)
        if len(kept) < len(history):
            affected.append((c, history, kept))
    print(f'Fichas fusionadas vigentes: {total}')
    print(f'Fichas con empleos duplicados según la regla propuesta: {len(affected)}')
    for c, history, kept in affected:
        print(f"\n--- {c['full_name']} ({c['id']}) fusionada {c.get('last_merge_at')}: {len(history)} → {len(kept)}")
        if TARGET and TARGET.lower() not in (c['full_name'] or '').lower():
            continue
        print('    ACTUALES:')
        for p in history:
            print(f"      · {p.get('company_name')} | {p.get('title')} | {p.get('start_date')} → {p.get('end_date') or 'actual'}"
                  f" | norm={normalize_company(p.get('company_name'))}")
        print('    QUEDARÍAN:')
        for p in kept:
            print(f"      · {p.get('company_name')} | {p.get('title')} | {p.get('start_date')} → {p.get('end_date') or 'actual'}")


asyncio.run(main())
