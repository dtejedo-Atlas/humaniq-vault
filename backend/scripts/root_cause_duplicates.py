"""Causa raíz (SOLO LECTURA) de los empleos repetidos con regla estricta (±2 meses).

Para cada ficha afectada cruza:
- `cv_versions.parsed_snapshot`: ¿el duplicado ya venía del parser en la primera extracción?
- `candidates_backup_20261007_2222`: ¿ya estaba el 7-oct?
- `cleanup_audit_log` / fichas con `duplicate_of`: ¿pasó por la limpieza de CV idéntico
  (`fill_missing_from_extras`, que agrega empleos sin deduplicar)?
- `merge_audit_log`, `cv_reprocessing_runs`, número de versiones de CV.

No escribe nada. Uso: python scripts/root_cause_duplicates.py
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

REPORT = '/app/test_reports/root_cause_duplicates.json'


def key(entry):
    return (str(entry.get('company_name') or '').strip().lower(),
            str(entry.get('title') or '').strip().lower(),
            str(entry.get('start_date') or ''), str(entry.get('end_date') or ''))


def describe(entry):
    return (f"{entry.get('title') or 'sin título'} @ {entry.get('company_name') or 'sin empresa'} "
            f"({entry.get('start_date') or '?'} → {entry.get('end_date') or 'presente'})")


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]

    # Fichas que quedaron como "conservadas" en limpiezas de CV idéntico
    kept_in_cleanup = set()
    async for doc in db.candidates.find({'duplicate_of': {'$exists': True}}, {'_id': 0, 'duplicate_of': 1}):
        kept_in_cleanup.add(doc['duplicate_of'])

    causas = {}
    rows = []
    async for c in db.candidates.find({'is_deleted': {'$ne': True}, 'last_merge_at': {'$exists': False}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'previous_companies': 1,
                                       'resume_files': 1, 'created_at': 1, 'source': 1}):
        groups = strict_duplicates(c.get('previous_companies') or [])
        if not groups:
            continue

        versions = await db.cv_versions.find({'candidate_id': c['id']},
                                             {'_id': 0, 'version': 1, 'parsed_snapshot': 1,
                                              'uploaded_at': 1, 'upload_source': 1}).to_list(20)
        snapshot_dup, primera_version = False, None
        for version in sorted(versions, key=lambda v: v.get('version') or 0):
            parsed = (version.get('parsed_snapshot') or {}).get('previous_companies') or []
            if primera_version is None:
                primera_version = {'version': version.get('version'), 'empleos': len(parsed),
                                   'fecha': version.get('uploaded_at'), 'origen': version.get('upload_source')}
            if strict_duplicates(parsed):
                snapshot_dup = True

        backup = await db.candidates_backup_20261007_2222.find_one({'id': c['id']},
                                                                  {'_id': 0, 'previous_companies': 1})
        backup_dup = bool(strict_duplicates((backup or {}).get('previous_companies') or [])) if backup else None
        reprocesos = await db.cv_reprocessing_runs.count_documents({'candidate_id': c['id']})

        if snapshot_dup:
            causa = 'parser: la extracción original ya traía el empleo repetido'
        elif c['id'] in kept_in_cleanup:
            causa = 'limpieza de CV idéntico: fill_missing_from_extras agregó empleos sin deduplicar'
        elif reprocesos:
            causa = 'reprocesamiento de CV'
        elif len(c.get('resume_files') or []) > 1:
            causa = 'nueva versión de CV'
        else:
            causa = 'sin evidencia (una sola versión, sin limpieza ni reproceso)'
        causas[causa] = causas.get(causa, 0) + 1

        rows.append({'candidate_id': c['id'], 'nombre': c.get('full_name'), 'causa': causa,
                     'creada': c.get('created_at'), 'versiones_cv': len(c.get('resume_files') or []),
                     'versiones_registradas': len(versions), 'primera_version': primera_version,
                     'duplicado_en_parse_original': snapshot_dup,
                     'duplicado_el_7_oct': backup_dup, 'reprocesos': reprocesos,
                     'conservada_en_limpieza_cv_identico': c['id'] in kept_in_cleanup,
                     'empleos_repetidos': [[describe(e) for e in g] for g in groups]})

    print(f"Fichas analizadas con empleos repetidos (regla estricta): {len(rows)}\n")
    print('CAUSA RAÍZ POR FICHA:')
    for causa, total in sorted(causas.items(), key=lambda kv: -kv[1]):
        print(f"  {total:>4}  {causa}")

    print('\n10 EJEMPLOS:')
    for row in rows[:10]:
        print(f"\n· {row['nombre']}  ({row['candidate_id']})")
        print(f"  causa: {row['causa']}")
        print(f"  creada: {row['creada']} · versiones de CV: {row['versiones_cv']} "
              f"· reprocesos: {row['reprocesos']} · duplicado el 7-oct: {row['duplicado_el_7_oct']}")
        print(f"  primera versión registrada: {row['primera_version']}")
        for group in row['empleos_repetidos']:
            for item in group:
                print(f"    - {item}")
            print('    ---')

    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump({'causas': causas, 'detalle': rows}, handle, ensure_ascii=False, default=str, indent=1)
    print(f"\nReporte: {REPORT}  (solo lectura)")


if __name__ == '__main__':
    asyncio.run(main())
