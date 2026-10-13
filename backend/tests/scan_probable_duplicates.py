"""Escaneo de duplicados probables en TODA la base. Solo lectura: no fusiona ni borra."""
import asyncio
import os
import sys
from datetime import date

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from probable_duplicates import _digits, _first_last, _norm_name, duplicate_reason  # noqa: E402

TODAY = date.today()


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    candidates = await db.candidates.find(
        {'is_deleted': {'$ne': True}},
        {'_id': 0, 'id': 1, 'full_name': 1, 'email': 1, 'phone': 1, 'previous_companies': 1, 'created_at': 1}
    ).to_list(5000)
    print(f'Candidatos vigentes revisados: {len(candidates)}')

    buckets = {}
    for c in candidates:
        keys = set()
        email = (c.get('email') or '').strip().lower()
        phone = _digits(c.get('phone'))
        tokens = _norm_name(c.get('full_name')).split()
        if email:
            keys.add(f'e:{email}')
        if phone:
            keys.add(f'p:{phone}')
        if tokens:
            keys.add(f'n:{tokens[0]}')
            keys.add(f'l:{tokens[-1]}')
        core = _first_last(c.get('full_name'))
        if core:
            keys.add(f'c:{core[0]}|{core[1]}')
        for key in keys:
            buckets.setdefault(key, []).append(c)

    seen, pairs = set(), []
    for group in buckets.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                key = tuple(sorted((a['id'], b['id'])))
                if key in seen:
                    continue
                seen.add(key)
                reason = duplicate_reason(a, b, TODAY)
                if reason:
                    pairs.append((a, b, reason))

    print(f'Pares probables encontrados: {len(pairs)}  (NO se fusionó ni borró nada)\n')
    width = 34
    print('CANDIDATO A'.ljust(width) + 'CANDIDATO B'.ljust(width) + 'MOTIVO')
    print('-' * 130)
    for a, b, reason in sorted(pairs, key=lambda p: (p[0].get('full_name') or '')):
        print((a.get('full_name') or '')[:width - 2].ljust(width) +
              (b.get('full_name') or '')[:width - 2].ljust(width) + reason[:60])
    print('\nIDs para la herramienta de fusión:')
    for a, b, _ in sorted(pairs, key=lambda p: (p[0].get('full_name') or '')):
        print(f"  {a['id']}  ↔  {b['id']}   ({a.get('full_name')} / {b.get('full_name')})")


asyncio.run(main())
