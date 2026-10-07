"""Diagnóstico (solo lectura): candidatos con experiencia en industrias objetivo en los últimos 10 años.

Revisa previous_companies (nombre, puesto, descripción), industry actual y texto completo del CV
(caché privada de scripts/cv_text_cache.py). Muestra la posición actual en v3 y v2 para la vacante.

Uso: python scripts/industry_scan.py --job <job_id> --industries telecommunications,technology,fintech
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import get_db  # noqa: E402
from scoring.engine_v3 import score_v3  # noqa: E402

CV_TEXTS = Path("/root/humaniq_cv_diagnosis/cv_texts.json")

KEYWORDS = {
    "telecommunications": [
        r"telecom", r"telecomunicaci", r"telefon[ií]a", r"\btelcel\b", r"\bmovistar\b", r"\bat&t\b", r"\batt\b",
        r"\baxtel\b", r"\bizzi\b", r"\btotalplay\b", r"\bmegacable\b", r"\btelmex\b", r"am[eé]rica m[oó]vil",
        r"\bericsson\b", r"\bnokia\b", r"\bhuawei\b", r"fibra [oó]ptica", r"\bmvno\b", r"operador m[oó]vil",
        r"\bdiri\b", r"\balt[aá]n\b", r"\btelef[oó]nica\b", r"\balestra\b", r"\bmaxcom\b", r"\bbestel\b",
        r"\bmarcatel\b", r"\bdish\b", r"\bsky m[eé]xico\b", r"\b5g\b", r"\blte\b", r"\bcarrier\b", r"\bisp\b",
        r"red(es)? de telecom", r"\bnextel\b", r"\biusacell\b", r"\bunefon\b", r"\bgtd\b", r"\bbait\b",
    ],
    "technology": [
        r"tecnolog[ií]a de la informaci", r"\bsoftware\b", r"\bsaas\b", r"\bcloud\b", r"\bnube\b", r"ciberseguridad",
        r"cybersecurity", r"data ?center", r"\bmicrosoft\b", r"\boracle\b", r"\bsap\b", r"\bibm\b", r"\bgoogle\b",
        r"\baws\b", r"\bamazon web", r"\bsofttek\b", r"\bglobant\b", r"\bkio\b", r"hewlett", r"\bhp\b", r"\bdell\b",
        r"\blenovo\b", r"\bintel\b", r"\bcisco\b", r"\bsalesforce\b", r"empresa tecnol[oó]gica", r"\bstartup tecnol",
        r"plataforma digital", r"soluciones tecnol[oó]gicas", r"\bti\b.*(empresa|servicios)", r"\bit services\b",
        r"\bneoris\b", r"\bindra\b", r"\baccenture\b", r"\btcs\b", r"\binfosys\b", r"\bwipro\b", r"\bcapgemini\b",
        r"\bsiemens\b", r"\bxerox\b", r"\bepson\b", r"\bcanon\b", r"\bsamsung\b", r"\bapple\b", r"\bmeta\b",
        r"\bmercado ?libre\b", r"\brappi\b", r"\buber\b", r"\bdidi\b", r"e-?commerce", r"\bmarketplace\b",
        r"inteligencia artificial", r"\btech\b", r"\bdigital transformation\b", r"transformaci[oó]n digital",
    ],
    "fintech": [
        r"\bfintech\b", r"pagos digitales", r"\bpayments?\b", r"\bwallet\b", r"billetera digital", r"\bclip\b",
        r"\bkonf[ií]o\b", r"\bkueski\b", r"\bstori\b", r"\bnu ?bank\b", r"\bnu m[eé]xico\b", r"mercado ?pago",
        r"\bopenpay\b", r"\bconekta\b", r"\bpaypal\b", r"\bbitso\b", r"cr[eé]dito digital", r"\bneobanco\b",
        r"\balbo\b", r"\bklar\b", r"\bcredijusto\b", r"\bcovalto\b", r"\bbanca digital\b", r"\bevertec\b",
        r"\bprosa\b", r"\bgetnet\b", r"\bbillpocket\b", r"\bsr\.? ?pago\b", r"\bpayclip\b", r"\bbnpl\b",
        r"\bcrypto\b", r"\bblockchain\b", r"\bbaz\b", r"\bueno\b", r"\bplata\b.*tarjeta", r"\brappi ?card\b",
        r"\bmercado ?cr[eé]dito\b", r"\bkapital\b", r"\bminu\b", r"\bbelvo\b", r"\bopen banking\b",
    ],
}

NOW = datetime(2026, 6, 1)


def _parse(d):
    if not d:
        return None
    s = str(d).strip().lower()
    if s in ("present", "presente", "actual", "actualidad", "current", "now", "hoy", "a la fecha"):
        return NOW
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?", s)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2) or 1), 1)


def _hits(text, ind):
    text = (text or "").lower()
    return [k for k in KEYWORDS[ind] if re.search(k, text)]


def scan_candidate(c, inds, cv_text):
    evidence = []
    cutoff = datetime(NOW.year - 10, NOW.month, 1)
    for pc in c.get("previous_companies") or []:
        end = _parse(pc.get("end_date")) or NOW
        start = _parse(pc.get("start_date"))
        if end < cutoff:
            continue
        blob = " ".join(str(pc.get(k) or "") for k in ("company_name", "title", "description"))
        for ind in inds:
            h = _hits(blob, ind)
            if h:
                years = round(((end - (start or end)).days) / 365.25, 1) if start else None
                evidence.append({"source": "previous_companies", "industry": ind, "company": pc.get("company_name"),
                                 "title": pc.get("title"), "start": pc.get("start_date"), "end": pc.get("end_date"),
                                 "years": years, "keywords": h[:3]})
    if c.get("industry") in inds:
        evidence.append({"source": "industry_field", "industry": c.get("industry"), "company": c.get("current_company"),
                         "title": c.get("current_title")})
    cv_hits = {}
    for ind in inds:
        h = _hits(cv_text, ind)
        if h:
            cv_hits[ind] = h[:4]
    return evidence, cv_hits


async def v2_rank(job, limit=200):
    os.environ.setdefault("ATLAS_URI", os.environ.get("ATLAS_URI", ""))
    from motor.motor_asyncio import AsyncIOMotorClient
    from job_matching_service import JobMatchingService
    from embedding_service import EmbeddingService
    url = os.environ.get("ATLAS_URI") or os.environ["MONGO_URL"]
    name = os.environ.get("ATLAS_DB_NAME") if os.environ.get("ATLAS_URI") else os.environ["DB_NAME"]
    adb = AsyncIOMotorClient(url)[name]
    svc = JobMatchingService(adb, EmbeddingService())
    res = await svc.match_candidates(job=job, threshold=0, limit=limit)
    return {r["candidate_id"]: (i + 1, r.get("match_percentage")) for i, r in enumerate(res.get("results") or [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--industries", default="telecommunications,technology,fintech")
    ap.add_argument("--out", default="/app/test_reports/industry_scan.json")
    a = ap.parse_args()
    inds = a.industries.split(",")
    db = get_db()
    job = db.jobs.find_one({"id": a.job}, {"_id": 0})
    cands = list(db.candidates.find({"is_deleted": {"$ne": True}}, {"_id": 0}))
    texts = json.loads(CV_TEXTS.read_text()) if CV_TEXTS.exists() else {}

    v3 = []
    for c in cands:
        r = score_v3(c, job)
        v3.append((c["id"], r["match_score_v3"], r["component_breakdown"]["IA"]["raw"]))
    v3.sort(key=lambda x: -x[1])
    v3_pos = {cid: (i + 1, hms, ia) for i, (cid, hms, ia) in enumerate(v3)}
    try:
        v2_pos = asyncio.run(v2_rank(job))
    except Exception as e:  # noqa: BLE001
        print("v2 no disponible:", e)
        v2_pos = {}

    rows, per_ind = [], {i: 0 for i in inds}
    for c in cands:
        ev, cv_hits = scan_candidate(c, inds, (texts.get(c["id"]) or {}).get("text", ""))
        if not ev and not cv_hits:
            continue
        strong = sorted({e["industry"] for e in ev})
        for i in strong:
            per_ind[i] += 1
        p3 = v3_pos.get(c["id"])
        p2 = v2_pos.get(c["id"])
        rows.append({
            "id": c["id"], "name": c.get("full_name"), "current_title": c.get("current_title"),
            "current_company": c.get("current_company"), "industry_field": c.get("industry"),
            "functional_area": c.get("functional_area"), "seniority": c.get("seniority"),
            "strong_industries": strong, "evidence": ev, "cv_text_only": cv_hits if not ev else {},
            "v3_rank": p3[0] if p3 else None, "v3_hms": p3[1] if p3 else None, "v3_ia_raw": p3[2] if p3 else None,
            "v2_rank": p2[0] if p2 else None, "v2_pct": p2[1] if p2 else None,
        })
    rows.sort(key=lambda r: (0 if r["strong_industries"] else 1, r["v3_rank"] or 9999))
    by_id = {c["id"]: c for c in cands}
    top10_v3 = [{"rank": i + 1, "name": by_id[cid].get("full_name"), "title": by_id[cid].get("current_title"),
                 "company": by_id[cid].get("current_company"), "industry": by_id[cid].get("industry"), "hms": hms,
                 "ia_raw": ia} for i, (cid, hms, ia) in enumerate(v3[:10])]
    top_v2 = sorted(v2_pos.items(), key=lambda kv: kv[1][0])[:10]
    top10_v2 = [{"rank": p, "name": by_id.get(cid, {}).get("full_name"), "title": by_id.get(cid, {}).get("current_title"),
                 "company": by_id.get(cid, {}).get("current_company"), "industry": by_id.get(cid, {}).get("industry"),
                 "pct": pct} for cid, (p, pct) in top_v2]
    out = {"job": {k: job.get(k) for k in ("id", "title", "company", "industry", "functional_area", "seniority",
                                            "min_experience", "job_scorecard", "required_skills")},
           "total_active": len(cands), "cv_texts_available": sum(1 for v in texts.values() if v.get("text")),
           "found_per_industry_structured": per_ind,
           "found_structured_total": sum(1 for r in rows if r["strong_industries"]),
           "found_cv_text_only": sum(1 for r in rows if not r["strong_industries"]),
           "top10_v3_current": top10_v3, "top10_v2_current": top10_v2, "candidates": rows}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "candidates"}, ensure_ascii=False, indent=1, default=str))
    print("\n=== Con evidencia estructurada (previous_companies / industry) ===")
    for r in rows:
        if r["strong_industries"]:
            ev = "; ".join(f"{e.get('company')} ({e.get('industry')}, {e.get('start')}→{e.get('end')}, {e.get('years')}a)"
                           for e in r["evidence"][:3])
            print(f"v3 #{r['v3_rank']} HMS {r['v3_hms']} | v2 #{r['v2_rank']} {r['v2_pct']}% | {r['name']} — {r['current_title']} @ {r['current_company']} | {ev}")
    print(f"\n=== Solo mención en texto del CV (requiere validación): {out['found_cv_text_only']} ===")
    for r in rows:
        if not r["strong_industries"]:
            print(f"v3 #{r['v3_rank']} HMS {r['v3_hms']} | {r['name']} — {r['current_title']} | {r['cv_text_only']}")


if __name__ == "__main__":
    main()
