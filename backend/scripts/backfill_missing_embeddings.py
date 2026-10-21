"""Rellena el campo `embedding` de los candidatos activos que no lo tienen.

Solo escribe `embedding` y `embedding_updated_at`. No modifica ningún otro campo.
Sin --apply es una simulación (no escribe nada).

Uso:
    python3 -m scripts.backfill_missing_embeddings            # dry-run
    python3 -m scripts.backfill_missing_embeddings --apply
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from embedding_service import embedding_service  # noqa: E402


async def main(apply: bool):
    client = AsyncIOMotorClient(os.environ['ATLAS_URI'])
    db = client[os.environ.get('ATLAS_DB_NAME') or os.environ['DB_NAME']]

    query = {
        'is_deleted': {'$ne': True},
        '$or': [{'embedding': {'$exists': False}}, {'embedding': None}],
    }
    pending = await db.candidates.find(query).to_list(length=None)
    print(f"Candidatos activos sin embedding: {len(pending)}")

    ok, failed = 0, []
    for c in pending:
        name = c.get('full_name') or c.get('id')
        if not apply:
            print(f"  [simulacion] {name}")
            continue
        try:
            emb = await embedding_service.generate_candidate_embedding(c)
            if not emb:
                failed.append((name, 'sin embedding devuelto'))
                continue
            await db.candidates.update_one(
                {'id': c['id']},
                {'$set': {
                    'embedding': emb,
                    'embedding_updated_at': datetime.now(timezone.utc).isoformat(),
                }},
            )
            ok += 1
            print(f"  [ok] {name}")
        except Exception as e:
            failed.append((name, str(e)[:120]))
            print(f"  [error] {name}: {str(e)[:120]}")

    if apply:
        total = await db.candidates.count_documents({'is_deleted': {'$ne': True}})
        with_emb = await db.candidates.count_documents({
            'is_deleted': {'$ne': True},
            'embedding': {'$exists': True, '$ne': None},
        })
        print(f"\nGenerados: {ok} | Fallidos: {len(failed)}")
        for n, err in failed:
            print(f"  - {n}: {err}")
        print(f"Cobertura final: {with_emb}/{total} candidatos activos con embedding")

    client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.apply))
