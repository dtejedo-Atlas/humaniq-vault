"""Re-parseo de las fichas sin empleos o sin años de experiencia (flujo normal de parseo).

- Respalda el documento COMPLETO antes de escribir: colección `reparse_backups` + archivo JSON
  en /app/memory/backups/reparse_empty_<fecha>.json.
- Solo RELLENA lo que está vacío (historial laboral, años, puesto/empresa actual, skills,
  idiomas, educación, contacto). Nunca sobrescribe un valor ya capturado ni la clasificación.
- Sin `--apply` solo simula.

Uso: python scripts/reparse_empty_candidates.py [--apply]
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
import resume_read_safety as rrs  # noqa: E402
from atlas_service import AtlasAIService  # noqa: E402
from server import clean_previous_companies  # noqa: E402

APPLY = '--apply' in sys.argv
STAMP = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
BACKUP = f'/app/memory/backups/reparse_empty_{STAMP}.json'
REPORT = '/app/test_reports/reparse_empty_candidates.json'

# Campos que se rellenan solo si están vacíos en la ficha
FILL_FIELDS = ('previous_companies', 'years_experience', 'current_title', 'current_company',
               'email', 'phone', 'linkedin_url', 'skills', 'languages', 'education', 'city')


def is_empty(value):
    return value in (None, '', 0, [], {})


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    ai = AtlasAIService()

    targets = []
    async for c in db.candidates.find({'is_deleted': {'$ne': True}}, {'_id': 0}):
        history = [e for e in (c.get('previous_companies') or []) if isinstance(e, dict)]
        if not history or c.get('years_experience') in (None, '', 0):
            targets.append(c)
    print(f"Fichas objetivo: {len(targets)}  ({'APLICANDO' if APPLY else 'SIMULACIÓN'})\n")

    backups, rows = [], []
    for c in targets:
        row = {'id': c['id'], 'nombre': c.get('full_name'),
               'antes': {'empleos': len([e for e in (c.get('previous_companies') or []) if isinstance(e, dict)]),
                         'anios': c.get('years_experience'),
                         'puesto': c.get('current_title'), 'empresa': c.get('current_company')}}
        try:
            extraction = await rrs.readable_resume(db, c)
            if isinstance(extraction, tuple):
                extraction = extraction[0]
            text = extraction.get('text') if isinstance(extraction, dict) else extraction
            parsed = await ai.parse_resume(text)
            if parsed.get('error'):
                raise ValueError(parsed['error'])
        except Exception as error:
            row['error'] = f"{type(error).__name__}: {error}"
            row['despues'] = row['antes']
            rows.append(row)
            print(f"· {row['nombre']:<34} ERROR {row['error'][:60]}")
            continue

        updates = {}
        for field in FILL_FIELDS:
            value = parsed.get(field)
            if is_empty(c.get(field)) and not is_empty(value):
                updates[field] = clean_previous_companies(value) if field == 'previous_companies' else value
        row['campos_rellenados'] = sorted(updates.keys())
        row['despues'] = {'empleos': len(updates.get('previous_companies', c.get('previous_companies') or [])),
                          'anios': updates.get('years_experience', c.get('years_experience')),
                          'puesto': updates.get('current_title', c.get('current_title')),
                          'empresa': updates.get('current_company', c.get('current_company'))}
        row['no_sobrescrito'] = sorted(f for f in FILL_FIELDS
                                       if not is_empty(c.get(f)) and not is_empty(parsed.get(f)))
        rows.append(row)
        print(f"· {row['nombre']:<34} empleos {row['antes']['empleos']} → {row['despues']['empleos']} · "
              f"años {row['antes']['anios']} → {row['despues']['anios']} · campos: {', '.join(row['campos_rellenados']) or 'ninguno'}")

        if APPLY and updates:
            backups.append(c)
            await db.reparse_backups.insert_one({'stamp': STAMP, 'candidate_id': c['id'], 'before': c})
            updates['updated_at'] = datetime.now(timezone.utc).isoformat()
            updates['reparsed_at'] = STAMP
            await db.candidates.update_one({'id': c['id'], 'is_deleted': {'$ne': True}}, {'$set': updates})

    if APPLY and backups:
        os.makedirs('/app/memory/backups', exist_ok=True)
        with open(BACKUP, 'w', encoding='utf-8') as handle:
            json.dump(backups, handle, ensure_ascii=False, default=str, indent=1)
        print(f"\nRespaldo completo: {BACKUP} + colección reparse_backups (stamp {STAMP})")

    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump({'aplicado': APPLY, 'stamp': STAMP, 'fichas': rows}, handle, ensure_ascii=False,
                  default=str, indent=1)
    print(f"Reporte: {REPORT}")
    if not APPLY:
        print('Nada se escribió. Corre con --apply para guardar.')


if __name__ == '__main__':
    asyncio.run(main())
