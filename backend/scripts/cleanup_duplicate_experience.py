"""Limpieza de los empleos repetidos históricos (causa: limpieza de CV idéntico).

Alcance: SOLO las fichas que quedaron como "conservadas" en una limpieza de CV idéntico
(`duplicate_of` apuntando a ellas). Para cada una:
 1. Si existe una foto del historial ANTERIOR a la limpieza (`cv_versions.parsed_snapshot`) y la
    ficha no recibió un CV nuevo después → se restaura esa foto, siempre que ningún empleo actual
    se pierda sin estar repetido (validación obligatoria).
 2. Si no hay foto, hubo CV nuevo después, o la restauración perdería un empleo legítimo →
    se aplica la regla estricta (mismo empleador + inicio ±2 meses + fin ±2 meses), conservando la
    entrada con la descripción más larga y anotando los títulos distintos.
Las fichas sin evidencia de esa limpieza NO se tocan: quedan listadas para revisión manual.

Respaldo antes de escribir: `previous_companies_pre_dedupe` (si no existía) + colección
`experience_cleanup_backups`. Los años de experiencia NO se modifican (solo se reportan).

Uso: python scripts/cleanup_duplicate_experience.py [--apply]
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
from experience_dedupe import (collapse_strict_duplicates, experience_years_from_history,  # noqa: E402
                               strict_duplicates, _range, same_company)

APPLY = '--apply' in sys.argv
STAMP = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
REPORT = '/app/test_reports/cleanup_duplicate_experience.json'
BACKUP = f'/app/memory/backups/experience_cleanup_{STAMP}.json'
ESPERADO = 843          # empleos repetidos medidos en el diagnóstico
TOLERANCIA = 0.05       # ±5%


def describe(entry):
    return (f"{entry.get('title') or 'sin título'} @ {entry.get('company_name') or 'sin empresa'} "
            f"({entry.get('start_date') or '?'} → {entry.get('end_date') or 'presente'})")


def matches_any(entry, pool, tolerance=2):
    """¿El empleo está representado en la foto (mismo empleador y fechas dentro de ±N meses)?"""
    start, end = _range(entry)
    for other in pool:
        o_start, o_end = _range(other)
        if not same_company(entry.get('company_name'), other.get('company_name')):
            continue
        if start is None or o_start is None:
            if start is None and o_start is None:
                return True
            continue
        if abs(start - o_start) > tolerance:
            continue
        if (end is None) != (o_end is None):
            continue
        if end is not None and abs(end - o_end) > tolerance:
            continue
        return True
    return False


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]

    # Fichas conservadas en limpiezas de CV idéntico y cuándo se hizo la limpieza
    cleanup_at = {}
    async for extra in db.candidates.find({'duplicate_of': {'$exists': True}},
                                          {'_id': 0, 'duplicate_of': 1, 'deleted_at': 1}):
        keep_id, when = extra['duplicate_of'], str(extra.get('deleted_at') or '')
        cleanup_at[keep_id] = max(cleanup_at.get(keep_id, ''), when)

    tocadas, manual, rows = 0, [], []
    empleos_eliminados = 0

    async for c in db.candidates.find({'is_deleted': {'$ne': True}, 'last_merge_at': {'$exists': False}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'previous_companies': 1,
                                       'years_experience': 1, 'previous_companies_pre_dedupe': 1,
                                       'resume_files': 1}):
        history = [e for e in (c.get('previous_companies') or []) if isinstance(e, dict)]
        if not strict_duplicates(history):
            continue
        if c['id'] not in cleanup_at:
            manual.append({'id': c['id'], 'nombre': c.get('full_name'), 'empleos': len(history),
                           'motivo': 'sin evidencia de limpieza de CV idéntico'})
            continue

        when = cleanup_at[c['id']]
        versions = await db.cv_versions.find({'candidate_id': c['id']},
                                             {'_id': 0, 'version': 1, 'uploaded_at': 1,
                                              'parsed_snapshot': 1}).to_list(50)
        cv_nuevo_despues = any(str(v.get('uploaded_at') or '') > when for v in versions)
        foto, foto_version = None, None
        for version in sorted(versions, key=lambda v: str(v.get('uploaded_at') or '')):
            if str(version.get('uploaded_at') or '') > when:
                continue
            snapshot = [e for e in ((version.get('parsed_snapshot') or {}).get('previous_companies') or [])
                        if isinstance(e, dict)]
            if snapshot:
                foto, foto_version = snapshot, version.get('version')

        estrategia, kept = None, None
        if foto and not cv_nuevo_despues:
            perdidos = [e for e in history if not matches_any(e, foto)]
            if not perdidos:
                estrategia, kept = f'restaurada foto previa (versión {foto_version})', list(foto)
            else:
                estrategia = ('colapso estricto (la foto perdería empleos: '
                              + '; '.join(describe(e) for e in perdidos[:3]) + ')')
        elif cv_nuevo_despues:
            estrategia = 'colapso estricto (hubo CV nuevo después de la limpieza)'
        else:
            estrategia = 'colapso estricto (sin foto previa)'
        if kept is None:
            kept = collapse_strict_duplicates(history)

        if len(kept) >= len(history):
            manual.append({'id': c['id'], 'nombre': c.get('full_name'), 'empleos': len(history),
                           'motivo': 'la regla estricta no eliminó nada'})
            continue

        tocadas += 1
        empleos_eliminados += len(history) - len(kept)
        rows.append({
            'candidate_id': c['id'], 'nombre': c.get('full_name'), 'estrategia': estrategia,
            'empleos_antes': len(history), 'empleos_despues': len(kept),
            'anios_antes': c.get('years_experience'),
            'anios_recalculado_referencia': experience_years_from_history(kept),
            'antes': [describe(e) for e in history], 'despues': [describe(e) for e in kept],
            'repetidos': [[describe(e) for e in g] for g in strict_duplicates(history)],
        })

        if APPLY:
            update = {'previous_companies': kept, 'experience_cleanup_at': STAMP,
                      'updated_at': datetime.now(timezone.utc).isoformat()}
            if not c.get('previous_companies_pre_dedupe'):
                update['previous_companies_pre_dedupe'] = history
            await db.experience_cleanup_backups.insert_one(
                {'stamp': STAMP, 'candidate_id': c['id'], 'before': history, 'after': kept,
                 'estrategia': estrategia})
            await db.candidates.update_one({'id': c['id'], 'is_deleted': {'$ne': True}}, {'$set': update})

    print(f"{'APLICANDO' if APPLY else 'SIMULACIÓN'}")
    print(f"Fichas a tocar: {tocadas} · empleos a eliminar: {empleos_eliminados} "
          f"(esperado {ESPERADO} ±{int(TOLERANCIA * 100)}%)")
    por_estrategia = {}
    for row in rows:
        clave = row['estrategia'].split(' (')[0]
        por_estrategia[clave] = por_estrategia.get(clave, 0) + 1
    for clave, total in sorted(por_estrategia.items(), key=lambda kv: -kv[1]):
        print(f"   {total:>4}  {clave}")
    print(f"Fichas para revisión manual (no se tocan): {len(manual)}")
    for item in manual:
        print(f"   · {item['nombre']} ({item['id']}) — {item['motivo']}")

    dentro = abs(empleos_eliminados - ESPERADO) <= ESPERADO * TOLERANCIA
    print(f"\n¿Total dentro del ±5% de {ESPERADO}? {'SÍ' if dentro else 'NO'}")

    print('\n10 EJEMPLOS ANTES / DESPUÉS:')
    for row in rows[:10]:
        print(f"\n· {row['nombre']} ({row['candidate_id']}) — {row['estrategia']}")
        print(f"  empleos {row['empleos_antes']} → {row['empleos_despues']} · "
              f"años {row['anios_antes']} (sin cambio; recálculo de referencia: {row['anios_recalculado_referencia']})")
        print('  ANTES:')
        for item in row['antes']:
            print(f"    - {item}")
        print('  DESPUÉS:')
        for item in row['despues']:
            print(f"    - {item}")

    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump({'aplicado': APPLY, 'stamp': STAMP, 'fichas_tocadas': tocadas,
                   'empleos_eliminados': empleos_eliminados, 'dentro_del_rango': dentro,
                   'revision_manual': manual, 'detalle': rows}, handle, ensure_ascii=False,
                  default=str, indent=1)
    print(f"\nReporte: {REPORT}")

    if APPLY and rows:
        os.makedirs('/app/memory/backups', exist_ok=True)
        with open(BACKUP, 'w', encoding='utf-8') as handle:
            json.dump(rows, handle, ensure_ascii=False, default=str, indent=1)
        print(f"Respaldo: {BACKUP} + colección experience_cleanup_backups (stamp {STAMP})")
    if not APPLY:
        print('Nada se escribió. Corre con --apply solo si el total está dentro del rango.')


if __name__ == '__main__':
    asyncio.run(main())
