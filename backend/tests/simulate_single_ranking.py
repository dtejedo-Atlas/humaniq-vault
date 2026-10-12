"""Simulación del motor único: top 15 antes/después para las vacantes indicadas.

Lee de Atlas, ejecuta la capa 3 (fit IA) sobre el top 30 y compara, sin activar la vista por defecto.
Uso: python tests/simulate_single_ranking.py "Director Comercial" "Director de Finanzas"
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
import server  # noqa: E402
from ai_refine_service import AIRefineService, _norm  # noqa: E402

TITLES = sys.argv[1:] or ['Director Comercial', 'Director de Finanzas']
TOP = 15


async def simulate(job):
    snapshot = await server.get_or_build_v3_snapshot(job, 'simulacion')
    v3 = snapshot.get('results') or []
    active_ko = {_norm(k['criterion']) for k in server.custom_knockouts_of(job)}
    refinements = await server.ai_refine_service.get(job['id'])
    criteria = refinements.get('criteria') or []

    before = AIRefineService.unify(v3, criteria, active_ko, None, False)
    fits = await server.fit_scores_for(job, snapshot, evaluate=True, force=True)
    after = AIRefineService.unify(v3, criteria, active_ko, fits, True)
    return before, after, fits


def table(title, rows, fits, before_pos=None):
    print(f'\n{title}')
    print(f"{'#':>3}  {'candidato':38} {'HMS':>4} {'fitIA':>5} {'final':>5}  {'calidad':10} {'acción':12} antes")
    print('-' * 110)
    for r in rows[:TOP]:
        fit = r.get('ai_fit')
        prev = before_pos.get(r['candidate_id']) if before_pos else None
        print(f"{r['rank']:>3}  {(r.get('candidate_name') or '')[:38]:38} {r.get('match_score_v3'):>4} "
              f"{(fit if fit is not None else '—'):>5} {r.get('final_score'):>5}  {r.get('quality'):10} "
              f"{r.get('action'):12} {('#' + str(prev)) if prev else ''}")
        if r.get('ai_warning'):
            print(f"      ⚠ {r['ai_warning'][:150]}")
        elif r.get('why'):
            print(f"      · {r['why'][:150]}")


async def main():
    total_cost = 0.0
    for title in TITLES:
        job = None
        if len(title) == 36 and title.count('-') == 4:
            job = await server.db.jobs.find_one({'id': title}, {'_id': 0})
        if not job:
            job = await server.db.jobs.find_one({'title': {'$regex': f'^{title}$', '$options': 'i'},
                                                 'status': 'active'}, {'_id': 0})
        if not job:
            job = await server.db.jobs.find_one({'title': {'$regex': title, '$options': 'i'}}, {'_id': 0})
        if not job:
            print(f'\n### {title}: vacante no encontrada')
            continue
        print(f"\n\n===== {job['title']} ({job.get('company') or 'sin empresa'}) — {job['id']} =====")
        before, after, fits = await simulate(job)
        cost = sum(f.get('cost_usd') or 0 for f in fits.values())
        total_cost += cost
        before_pos = {r['candidate_id']: r['rank'] for r in before}
        table('ANTES (HMS v3 + criterios IA)', before, fits)
        table('DESPUÉS (motor único: 0.75·HMS + 0.25·fit IA)', after, fits, before_pos)
        print(f"\nCVs leídos por la IA: {sum(1 for f in fits.values() if f.get('fit') is not None)}"
              f" de {len(fits)} · costo de esta corrida: ${cost:.2f}")
    print(f'\n\nCosto total de la simulación: ${total_cost:.2f}')


asyncio.run(main())
