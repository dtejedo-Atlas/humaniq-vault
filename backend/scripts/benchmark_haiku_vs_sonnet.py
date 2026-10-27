"""Compara Claude Haiku 5.5 vs el modelo actual (Sonnet 5.5) en CVs reales.

SOLO LECTURA: no escribe nada en base. Solo hace llamadas al LLM y compara.

Uso:
    python3 -m scripts.benchmark_haiku_vs_sonnet --n 3
"""
import argparse
import asyncio
import json
import os
import sys
import time

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from scripts.db_connection import get_db  # noqa: E402
import ai_model_config as amc  # noqa: E402
from ai_model_config import estimate_cost_usd  # noqa: E402
from atlas_service import atlas_service  # noqa: E402

CANDIDATES = ("claude-sonnet-5-5", "claude-haiku-5-5")


def force_model(model_id: str):
    async def _get_model(task: str) -> str:
        return model_id
    amc.ai_model_config.get_model = _get_model


def jobs_of(parsed: dict):
    out = []
    for e in parsed.get("previous_companies") or []:
        out.append((
            (e.get("company") or "").strip().lower(),
            (e.get("title") or "").strip().lower(),
            str(e.get("start_date") or "").strip(),
            str(e.get("end_date") or "").strip(),
        ))
    return out


async def run_one(service, model_id, text, parsed_for_class):
    force_model(model_id)
    t0 = time.time()
    parsed = await service.parse_resume(text)
    t_parse = time.time() - t0
    t0 = time.time()
    classified = await service.classify_candidate(parsed_for_class or parsed, text)
    t_class = time.time() - t0
    in_tok = len(text) // 4 + 1200          # misma convención que ai_refine_service
    out_tok = len(json.dumps(parsed, ensure_ascii=False)) // 4
    cost = (estimate_cost_usd(model_id, in_tok, out_tok)
            + estimate_cost_usd(model_id, len(text[:3000]) // 4 + 900, 200))
    return {"parsed": parsed, "classified": classified, "cost": cost,
            "secs": round(t_parse + t_class, 1)}


async def main(n: int):
    db = get_db()
    service = atlas_service

    docs = list(db.cv_fulltext.find({}).sort("extracted_at", -1).limit(60))
    picked = []
    for d in docs:
        c = db.candidates.find_one({"id": d["candidate_id"], "is_deleted": {"$ne": True}},
                                   {"_id": 0, "full_name": 1, "id": 1})
        if c and len(d.get("text") or "") > 1500:
            picked.append((c, d["text"]))
        if len(picked) >= n:
            break

    print(f"\nBENCHMARK Haiku 5.5 vs Sonnet 5.5 — {len(picked)} CVs reales (solo lectura)\n")
    totals = {m: {"cost": 0.0, "secs": 0.0} for m in CANDIDATES}

    for cand, text in picked:
        print("=" * 100)
        print(f"CV: {cand['full_name']}  ({len(text)} chars)")
        res = {}
        for m in CANDIDATES:
            res[m] = await run_one(service, m, text, None)
            totals[m]["cost"] += res[m]["cost"]
            totals[m]["secs"] += res[m]["secs"]

        s, h = res["claude-sonnet-5-5"], res["claude-haiku-5-5"]
        sp, hp = s["parsed"], h["parsed"]
        sc, hc = s["classified"], h["classified"]

        rows = [
            ("Nombre", sp.get("full_name"), hp.get("full_name")),
            ("Puesto actual", sp.get("current_title"), hp.get("current_title")),
            ("Empresa actual", sp.get("current_company"), hp.get("current_company")),
            ("Años de experiencia", sp.get("years_experience"), hp.get("years_experience")),
            ("Empleos extraídos", len(sp.get("previous_companies") or []),
             len(hp.get("previous_companies") or [])),
            ("Habilidades", len(sp.get("skills") or []), len(hp.get("skills") or [])),
            ("Industria", sc.get("industry"), hc.get("industry")),
            ("Área funcional", sc.get("functional_area"), hc.get("functional_area")),
            ("Subárea", sc.get("presentation_subarea"), hc.get("presentation_subarea")),
            ("Seniority", sc.get("seniority"), hc.get("seniority")),
        ]
        print(f"{'Campo':22s} {'Sonnet 5.5 (actual)':38s} {'Haiku 5.5':38s} =")
        for label, a, b in rows:
            same = "si" if str(a).strip().lower() == str(b).strip().lower() else "NO"
            print(f"{label:22s} {str(a)[:37]:38s} {str(b)[:37]:38s} {same}")

        sj, hj = jobs_of(sp), jobs_of(hp)
        same_jobs = sum(1 for j in hj if j in sj)
        print(f"{'Empleos idénticos':22s} {len(sj):<38d} {f'{same_jobs} de {len(hj)} coinciden':38s}")
        only_s = [f"{c} / {t} ({a}–{b})" for c, t, a, b in sj if (c, t, a, b) not in hj]
        only_h = [f"{c} / {t} ({a}–{b})" for c, t, a, b in hj if (c, t, a, b) not in sj]
        for x in only_s:
            print(f"   solo Sonnet: {x}")
        for x in only_h:
            print(f"   solo Haiku : {x}")
        print(f"{'Costo estimado USD':22s} {s['cost']:<38.5f} {h['cost']:<38.5f}")
        print(f"{'Segundos':22s} {s['secs']:<38.1f} {h['secs']:<38.1f}")

    print("\n" + "=" * 100)
    k = len(picked) or 1
    cs, ch = totals["claude-sonnet-5-5"]["cost"] / k, totals["claude-haiku-5-5"]["cost"] / k
    print(f"Promedio por CV — Sonnet 5.5: US${cs:.5f} | Haiku 5.5: US${ch:.5f} "
          f"| ahorro {0 if cs == 0 else (1 - ch / cs) * 100:.0f}%")
    print(f"Tiempo promedio — Sonnet 5.5: {totals['claude-sonnet-5-5']['secs'] / k:.1f}s | "
          f"Haiku 5.5: {totals['claude-haiku-5-5']['secs'] / k:.1f}s\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=3)
    asyncio.run(main(p.parse_args().n))
