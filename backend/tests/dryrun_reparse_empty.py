"""Re-parseo en MODO PRUEBA (no guarda nada) de fichas sin empleos o sin años de experiencia.

Por cada ficha: ¿el CV original es legible?, cuántos caracteres se extraen (nativo vs OCR),
y qué extraería el parser (empleos, años, puesto actual).

Uso: python tests/dryrun_reparse_empty.py
"""
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
import resume_read_safety as rrs  # noqa: E402
from atlas_service import AtlasAIService  # noqa: E402

REPORT = '/app/test_reports/dryrun_reparse_empty.json'


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    ai = AtlasAIService()

    targets = {}
    async for c in db.candidates.find({'is_deleted': {'$ne': True}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'years_experience': 1,
                                       'previous_companies': 1, 'resume_files': 1, 'current_title': 1}):
        history = [e for e in (c.get('previous_companies') or []) if isinstance(e, dict)]
        if not history or c.get('years_experience') in (None, '', 0):
            targets[c['id']] = c
    print(f"Fichas en modo prueba: {len(targets)} (sin empleos o sin años)\n")

    rows = []
    for c in targets.values():
        row = {'id': c['id'], 'nombre': c.get('full_name'),
               'empleos_actuales': len([e for e in (c.get('previous_companies') or []) if isinstance(e, dict)]),
               'anios_actuales': c.get('years_experience')}
        try:
            extraction = await rrs.readable_resume(db, c)
            if isinstance(extraction, tuple):
                extraction = extraction[0]
            text = extraction.get('text') if isinstance(extraction, dict) else extraction
            row['legible'] = True
            row['caracteres'] = len(text or '')
            row['metodo'] = [p.get('method') for p in (extraction.get('pages') or [])] \
                if isinstance(extraction, dict) else None
            parsed = await ai.parse_resume(text)
            row['empleos_extraidos'] = len(parsed.get('previous_companies') or [])
            row['anios_extraidos'] = parsed.get('years_experience')
            row['puesto_extraido'] = parsed.get('current_title')
            row['empresa_extraida'] = parsed.get('current_company')
        except Exception as error:
            row['legible'] = False
            row['motivo'] = f"{type(error).__name__}: {error}"
        rows.append(row)
        print(f"· {row['nombre']:<34} legible={row.get('legible')} "
              f"chars={row.get('caracteres', '—')} ocr={row.get('metodo')} "
              f"empleos {row['empleos_actuales']} → {row.get('empleos_extraidos', '—')} "
              f"años {row['anios_actuales']} → {row.get('anios_extraidos', '—')}"
              + (f"  [{row.get('motivo')}]" if not row.get('legible') else ''))

    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump(rows, handle, ensure_ascii=False, default=str, indent=1)
    print(f"\nReporte: {REPORT}  (modo prueba: no se escribió nada en Mongo)")


asyncio.run(main())
