#!/usr/bin/env python3
"""Bulk-approve de clasificaciones IA con confidence >= 0.85 + normalización taxonómica al slug canónico."""
import os
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / '.env')

from motor.motor_asyncio import AsyncIOMotorClient
from taxonomy import INDUSTRIES, FUNCTIONAL_AREAS

IND_KEYS = {i['key'] for i in INDUSTRIES}
AREA_KEYS = {a['key'] for a in FUNCTIONAL_AREAS}


def normalize(value, catalog):
    if not value:
        return value, False
    if value in catalog:
        return value, False
    slug = value.lower().strip().replace(' ', '_')
    if slug in catalog:
        return slug, True
    return value, False


async def main():
    client = AsyncIOMotorClient(os.environ['ATLAS_URI'])
    db = client[os.environ['ATLAS_DB_NAME']]

    admin = await db.users.find_one({'email': 'test_utf8@atlas.com'}, {'_id': 0, 'id': 1})
    approved_by = admin['id'] if admin else 'bulk_approve_script'
    now = datetime.now(timezone.utc).isoformat()

    q = {
        'is_deleted': {'$ne': True},
        'ai_classification.approved_by_recruiter': False,
        'ai_classification.confidence_score': {'$gte': 0.85},
    }
    mappings = Counter()
    unmappable = []
    approved = 0

    async for c in db.candidates.find(q, {'_id': 0, 'id': 1, 'full_name': 1, 'ai_classification': 1, 'industry': 1, 'functional_area': 1, 'seniority': 1, 'tags': 1}):
        ai = c['ai_classification']
        ind, ind_changed = normalize(ai.get('industry'), IND_KEYS)
        area, area_changed = normalize(ai.get('functional_area'), AREA_KEYS)

        if ai.get('industry') and ind not in IND_KEYS:
            unmappable.append((c['full_name'], 'industry', ai.get('industry')))
            continue
        if ai.get('functional_area') and area not in AREA_KEYS:
            unmappable.append((c['full_name'], 'functional_area', ai.get('functional_area')))
            continue

        if ind_changed:
            mappings[f"industry: {ai.get('industry')} -> {ind}"] += 1
        if area_changed:
            mappings[f"area: {ai.get('functional_area')} -> {area}"] += 1

        update = {
            'industry': ind or c.get('industry'),
            'functional_area': area or c.get('functional_area'),
            'seniority': ai.get('seniority') or c.get('seniority'),
            'tags': ai.get('suggested_tags') or c.get('tags', []),
            'ai_classification.industry': ind,
            'ai_classification.functional_area': area,
            'ai_classification.approved_by_recruiter': True,
            'ai_classification.approved_at': now,
            'ai_classification.approved_by': approved_by,
            'updated_at': now,
        }
        await db.candidates.update_one({'id': c['id']}, {'$set': update})
        approved += 1

    print(f"Aprobados: {approved}")
    print("\nMapeos aplicados:")
    for m, n in sorted(mappings.items()):
        print(f"  {m}  ({n} candidato{'s' if n > 1 else ''})")
    if unmappable:
        print("\nNO mapeables (quedan en bandeja):")
        for name, field, val in unmappable:
            print(f"  {name}: {field}='{val}'")

    rem_hi = await db.candidates.count_documents(q)
    rem_all = await db.candidates.count_documents({'is_deleted': {'$ne': True}, 'ai_classification.approved_by_recruiter': False})
    print(f"\nBandeja restante: {rem_all} total ({rem_hi} con conf >= 0.85)")


if __name__ == '__main__':
    asyncio.run(main())
