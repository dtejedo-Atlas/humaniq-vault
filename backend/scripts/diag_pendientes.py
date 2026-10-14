"""Diagnóstico SOLO LECTURA: años bajados por dedupe, caso Humberto, fichas sin empleos.

No escribe nada. Uso: python scripts/diag_pendientes.py
"""
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from experience_dedupe import dedupe_experience, is_same_job, normalize_company  # noqa: E402
from industry_trajectory import total_experience_years  # noqa: E402


def undated(history):
    return [e for e in history if isinstance(e, dict) and not e.get('start_date')]


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    out = {}

    # 1) Fichas cuyos años bajaron tras la deduplicación
    dropped = []
    async for c in db.candidates.find({'years_experience_pre_dedupe': {'$exists': True}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'years_experience': 1,
                                       'years_experience_pre_dedupe': 1, 'previous_companies': 1,
                                       'previous_companies_pre_dedupe': 1}):
        before, after = c.get('years_experience_pre_dedupe'), c.get('years_experience')
        if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after < before:
            dropped.append({'id': c['id'], 'nombre': c.get('full_name'), 'antes': before, 'despues': after,
                            'empleos_sin_fecha': len(undated(c.get('previous_companies') or [])),
                            'empleos': len(c.get('previous_companies') or []),
                            'empleos_antes': len(c.get('previous_companies_pre_dedupe') or [])})
    out['anios_bajados'] = sorted(dropped, key=lambda r: r['antes'] - r['despues'], reverse=True)
    print(f"\n1) Fichas con años de experiencia a la baja tras dedupe: {len(dropped)}")
    for row in out['anios_bajados']:
        print(f"   {row['nombre']:<38} {row['antes']} → {row['despues']}  "
              f"(empleos {row['empleos_antes']}→{row['empleos']}, sin fecha: {row['empleos_sin_fecha']})")

    # 2) Humberto Hernández
    print('\n2) Humberto Hernández')
    humbertos = await db.candidates.find({'full_name': {'$regex': 'humberto', '$options': 'i'},
                                          'is_deleted': {'$ne': True}}, {'_id': 0}).to_list(20)
    out['humberto'] = []
    for c in humbertos:
        history = c.get('previous_companies') or []
        kept = dedupe_experience(history)
        info = {'id': c['id'], 'nombre': c.get('full_name'), 'fusionada': bool(c.get('last_merge_at')),
                'dedupe_aplicado': c.get('experience_dedupe_at'), 'empleos': len(history),
                'empleos_dedupe': len(kept), 'years_experience': c.get('years_experience'),
                'detalle': [{'empresa': e.get('company_name'), 'norm': normalize_company(e.get('company_name')),
                             'titulo': e.get('title'), 'inicio': e.get('start_date'), 'fin': e.get('end_date')}
                            for e in history if isinstance(e, dict)]}
        pares = []
        for i, a in enumerate(history):
            for b in history[i + 1:]:
                if isinstance(a, dict) and isinstance(b, dict) and \
                        normalize_company(a.get('company_name')) == normalize_company(b.get('company_name')):
                    pares.append({'empresa': a.get('company_name'),
                                  'a': f"{a.get('title')} {a.get('start_date')}→{a.get('end_date')}",
                                  'b': f"{b.get('title')} {b.get('start_date')}→{b.get('end_date')}",
                                  'mismo_empleo': is_same_job(a, b)})
        info['pares_misma_empresa'] = pares
        out['humberto'].append(info)
        print(f"   {c.get('full_name')} ({c['id'][:8]}) fusionada={bool(c.get('last_merge_at'))} "
              f"dedupe={c.get('experience_dedupe_at')} empleos={len(history)} → dedupe={len(kept)}")
        for p in pares:
            print(f"      misma empresa '{p['empresa']}': [{p['a']}] vs [{p['b']}] → mismo_empleo={p['mismo_empleo']}")

    # 3) Simulación de dedupe en TODA la base (sin escribir)
    print('\n3) Simulación de dedupe en toda la base')
    total, con_duplicados, empleos_sobrantes, anios_a_la_baja, muestra = 0, 0, 0, 0, []
    async for c in db.candidates.find({'is_deleted': {'$ne': True}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'years_experience': 1,
                                       'previous_companies': 1, 'last_merge_at': 1}):
        total += 1
        history = c.get('previous_companies') or []
        kept = dedupe_experience(history)
        if len(kept) < len(history):
            con_duplicados += 1
            empleos_sobrantes += len(history) - len(kept)
            after = total_experience_years({**c, 'previous_companies': kept})
            before = c.get('years_experience')
            baja = isinstance(before, (int, float)) and after is not None and round(after) < before
            anios_a_la_baja += 1 if baja else 0
            if len(muestra) < 25:
                muestra.append({'id': c['id'], 'nombre': c.get('full_name'), 'empleos': len(history),
                                'empleos_dedupe': len(kept), 'anios_antes': before,
                                'anios_despues': None if after is None else round(after),
                                'fusionada': bool(c.get('last_merge_at')),
                                'empleos_sin_fecha': len(undated(history))})
    out['simulacion_global'] = {'candidatos_activos': total, 'con_duplicados': con_duplicados,
                                'empleos_sobrantes': empleos_sobrantes,
                                'fichas_con_anios_a_la_baja': anios_a_la_baja, 'muestra': muestra}
    print(f"   activos={total} con duplicados={con_duplicados} empleos sobrantes={empleos_sobrantes} "
          f"fichas cuyos años bajarían={anios_a_la_baja}")
    for row in muestra[:15]:
        print(f"   {row['nombre']:<38} {row['empleos']}→{row['empleos_dedupe']} empleos · "
              f"años {row['anios_antes']}→{row['anios_despues']} · sin fecha {row['empleos_sin_fecha']}")

    # 4) Fichas sin empleos o sin años de experiencia
    sin_empleos, sin_anios = [], []
    async for c in db.candidates.find({'is_deleted': {'$ne': True}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'years_experience': 1,
                                       'previous_companies': 1, 'current_company': 1, 'status': 1}):
        history = [e for e in (c.get('previous_companies') or []) if isinstance(e, dict)]
        years = c.get('years_experience')
        if not history:
            sin_empleos.append({'id': c['id'], 'nombre': c.get('full_name'),
                                'empresa_actual': c.get('current_company'), 'anios': years})
        if years in (None, '', 0):
            sin_anios.append({'id': c['id'], 'nombre': c.get('full_name'), 'empleos': len(history), 'anios': years})
    out['sin_empleos'] = sin_empleos
    out['sin_anios'] = sin_anios
    print(f"\n4) Fichas activas con 0 empleos: {len(sin_empleos)} · sin years_experience (null/0): {len(sin_anios)}")
    print('   Primeros 10 sin empleos: ' + ', '.join(r['nombre'] or r['id'][:8] for r in sin_empleos[:10]))
    print('   Primeros 10 sin años:    ' + ', '.join(r['nombre'] or r['id'][:8] for r in sin_anios[:10]))

    path = '/app/test_reports/pendientes_diagnostico.json'
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(out, handle, ensure_ascii=False, default=str, indent=1)
    print(f"\nReporte: {path}  (solo lectura, no se escribió nada en Mongo)")


if __name__ == '__main__':
    asyncio.run(main())
