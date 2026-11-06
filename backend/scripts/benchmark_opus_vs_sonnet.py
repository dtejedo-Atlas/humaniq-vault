"""Compara el Análisis IA del match con Opus 5.5 vs Sonnet 5.5. SOLO LECTURA.

Toma el ranking unificado real de una vacante (vía API), arma los mismos briefs que
`AIMatchReviewService.review()` y pide el análisis a ambos modelos, sin guardar nada.

Uso:
    python3 -m scripts.benchmark_opus_vs_sonnet --job <job_id>
"""
import argparse
import asyncio
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from scripts.db_connection import get_db  # noqa: E402
from ai_match_review_service import AIMatchReviewService  # noqa: E402
from ai_model_config import estimate_cost_usd  # noqa: E402
from auth import create_access_token  # noqa: E402

MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")


async def main(job_id: str, admin_email: str, api_base: str, top_n: int):
    db = get_db()
    job = db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        print(f"Vacante {job_id} no encontrada")
        return

    token = create_access_token({"sub": admin_email})
    r = requests.get(f"{api_base}/api/jobs/{job_id}/unified-matches",
                     headers={"Authorization": f"Bearer {token}"}, timeout=180)
    r.raise_for_status()
    rows = (r.json().get("results") or [])[:top_n]
    if not rows:
        print("El motor no devolvió candidatos para esta vacante")
        return

    refin = db.job_ai_refinements.find_one({"job_id": job_id}, {"_id": 0}) or {}
    criteria = [{"id": c["id"], "text": c["text"]} for c in (refin.get("criteria") or [])]
    ids = [x["candidate_id"] for x in rows]
    by_id = {d["id"]: d for d in db.candidates.find({"id": {"$in": ids}}, {"_id": 0, "embedding": 0})}

    svc = AIMatchReviewService(None, None, os.environ["EMERGENT_LLM_KEY"])
    briefs = [svc._unified_brief(row, i + 1, by_id.get(row["candidate_id"]), criteria)
              for i, row in enumerate(rows)]

    print(f"\nANÁLISIS IA DEL MATCH — Opus 5.5 vs Sonnet 5.5")
    print(f"Vacante: {job.get('title')} | finalistas: {len(briefs)} (solo lectura)\n")

    out = {}
    for m in MODELS:
        t0 = time.time()
        analysis = await svc._ask_claude(job, briefs, m)
        secs = time.time() - t0
        payload_chars = len(json.dumps(briefs, ensure_ascii=False)) + 4000
        out_chars = len(json.dumps(analysis, ensure_ascii=False))
        cost = estimate_cost_usd(m, payload_chars // 4, out_chars // 4)
        out[m] = {"a": analysis, "secs": secs, "cost": cost, "chars": out_chars}

    o, s = out["claude-opus-5-5"], out["claude-sonnet-5-5"]
    fo = {x["candidate_id"]: x for x in (o["a"].get("shortlist") or [])}
    fs = {x["candidate_id"]: x for x in (s["a"].get("shortlist") or [])}

    print(f"{'Finalista':30s} {'Fit Opus':10s} {'Fit Sonnet':11s} {'=':3s} "
          f"{'Fort. O/S':10s} {'Brechas O/S':12s} {'Riesgos O/S':12s}")
    print("-" * 95)
    same_fit = 0
    for b in briefs:
        cid = b["candidate_id"]
        a, c = fo.get(cid, {}), fs.get(cid, {})
        eq = "si" if a.get("fit") == c.get("fit") else "NO"
        same_fit += eq == "si"
        print(f"{(b['name'] or '')[:29]:30s} {str(a.get('fit')):10s} {str(c.get('fit')):11s} {eq:3s} "
              f"{len(a.get('strengths') or [])}/{len(c.get('strengths') or []):<9} "
              f"{len(a.get('gaps') or [])}/{len(c.get('gaps') or []):<11} "
              f"{len(a.get('risk_flags') or [])}/{len(c.get('risk_flags') or []):<11}")

    print(f"\nMismo veredicto de fit: {same_fit} de {len(briefs)}")
    print(f"Costo estimado  — Opus: US${o['cost']:.4f} | Sonnet: US${s['cost']:.4f} "
          f"(Opus cuesta {o['cost'] / max(s['cost'], 1e-9):.1f}x)")
    print(f"Tiempo          — Opus: {o['secs']:.1f}s | Sonnet: {s['secs']:.1f}s")
    print(f"Largo de salida — Opus: {o['chars']} chars | Sonnet: {s['chars']} chars")
    print(f"\n--- Resumen de terna (Opus) ---\n{o['a'].get('summary')}")
    print(f"\n--- Resumen de terna (Sonnet) ---\n{s['a'].get('summary')}")
    for cid in list(fo)[:2]:
        print(f"\n--- Veredicto de {fo[cid].get('candidate_id')[:8]} ---")
        print(f"Opus  : {fo[cid].get('verdict')}")
        print(f"Sonnet: {fs.get(cid, {}).get('verdict')}")
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--job", required=True)
    p.add_argument("--admin", default="dtejedo@gmail.com")
    p.add_argument("--api", required=True, help="base URL, ej. https://...preview.emergentagent.com")
    p.add_argument("--top", type=int, default=5)
    a = p.parse_args()
    asyncio.run(main(a.job, a.admin, a.api.rstrip("/"), a.top))
