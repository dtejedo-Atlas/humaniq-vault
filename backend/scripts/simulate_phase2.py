"""FASE 2 — Simulación en memoria (no escribe en la base ni toca scoring/).

Aplica: target_industries + industry_requirement, company_industry heurístico por empleo,
nueva IA por trayectoria, knockout de industria y pesos propuestos. Compara top 10 antes/después.

Uso: python scripts/simulate_phase2.py
"""
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import get_db  # noqa: E402
from scoring.engine_v3 import score_v3  # noqa: E402
from scoring.config_v3 import WEIGHTS_BY_PROCESS, SHRINKAGE_NEUTRAL, HEC_EXPONENT  # noqa: E402
from industry_trajectory import industry_affinity, industry_knockout, coverage_by_industry  # noqa: E402

NOW = datetime(2026, 6, 1)

PROPOSED_WEIGHTS = {
    "c_level":     {"SK": 0.05, "ER": 0.16, "FA": 0.14, "SA": 0.14, "IA": 0.17, "ED": 0.10, "TR": 0.06, "LO": 0.02, "SM": 0.03, "CQ": 0.03, "CC": 0.10},
    "executive":   {"SK": 0.08, "ER": 0.17, "FA": 0.15, "SA": 0.14, "IA": 0.17, "ED": 0.07, "TR": 0.05, "LO": 0.03, "SM": 0.04, "CQ": 0.02, "CC": 0.08},
    "managerial":  {"SK": 0.13, "ER": 0.17, "FA": 0.16, "SA": 0.13, "IA": 0.15, "ED": 0.06, "TR": 0.05, "LO": 0.03, "SM": 0.04, "CQ": 0.02, "CC": 0.06},
    "operational": {"SK": 0.22, "ER": 0.17, "FA": 0.15, "SA": 0.11, "IA": 0.12, "ED": 0.04, "TR": 0.05, "LO": 0.05, "SM": 0.04, "CQ": 0.02, "CC": 0.03},
}
for _p, _w in PROPOSED_WEIGHTS.items():
    assert abs(sum(_w.values()) - 1.0) < 1e-6, (_p, sum(_w.values()))

# Heurística de industria por nombre de empresa / descripción (proxy del backfill con Claude)
HEUR = {
    "telecommunications": [r"telecom", r"telecomunicaci", r"telefon[ií]a", r"\btelcel\b", r"\bmovistar\b", r"\bat&t\b", r"\baxtel\b", r"\bizzi\b", r"\btotalplay\b", r"\bmegacable\b", r"\btelmex\b", r"am[eé]rica m[oó]vil", r"\bericsson\b", r"\bnokia\b", r"\bhuawei\b", r"\bmvno\b", r"operador m[oó]vil", r"\bdiri\b", r"\balt[aá]n\b", r"\btelef[oó]nica\b", r"\balestra\b", r"\bmaxcom\b", r"\bbestel\b", r"\bmarcatel\b", r"\bdish\b", r"\bnextel\b", r"\biusacell\b", r"\bunefon\b", r"\bbait\b", r"\bvivoxie\b", r"\bsky\b"],
    "fintech": [r"\bfintech\b", r"pagos digitales", r"billetera digital", r"\bclip\b", r"\bkonf[ií]o\b", r"\bkueski\b", r"\bstori\b", r"\bnu ?bank\b", r"mercado ?pago", r"\bopenpay\b", r"\bconekta\b", r"\bpaypal\b", r"\bbitso\b", r"\bneobanco\b", r"\balbo\b", r"\bklar\b", r"\bcredijusto\b", r"\bcovalto\b", r"\bevertec\b", r"\bprosa\b", r"\bgetnet\b", r"\bbillpocket\b", r"\bkoin\b", r"\bbelvo\b", r"\bkapital\b"],
    "technology": [r"\bsoftware\b", r"technolog", r"tecnolog", r"\btech\b", r"\bsofttek\b", r"\bglobant\b", r"\bkio\b", r"hewlett", r"\bhp\b", r"\bdell\b", r"\blenovo\b", r"\bintel\b", r"\bcisco\b", r"\bibm\b", r"\bmicrosoft\b", r"\boracle\b", r"\bsap\b", r"\bgoogle\b", r"\bamazon\b", r"\baws\b", r"\bneoris\b", r"\bindra\b", r"\baccenture\b", r"\bcapgemini\b", r"\beveris\b", r"\bntt\b", r"\bsamsung\b", r"\bapple\b", r"\bmercado ?libre\b", r"\brappi\b", r"\buber\b", r"\bdidi\b", r"\bsaas\b", r"\bit services\b", r"\bcyber"],
    "financial_services": [r"\bbanco\b", r"\bbank\b", r"\bbanorte\b", r"\bbbva\b", r"\bsantander\b", r"\bhsbc\b", r"\bcitibanamex\b", r"\bbanamex\b", r"\bscotiabank\b", r"\bfinanciera\b", r"\bsofom\b", r"\bseguros\b", r"\baseguradora\b", r"\bafore\b", r"\bcasa de bolsa\b", r"\bgnp\b", r"\bmetlife\b", r"\bcr[eé]dito\b", r"\bcobranza\b", r"\bbanca\b", r"\bfinancial\b"],
    "manufacturing": [r"manufactur", r"\bf[aá]brica\b", r"\bplanta\b", r"industrial", r"\bmetal", r"\bacero\b", r"\bpl[aá]stic", r"\bempaque", r"\bpapel\b", r"\bqu[ií]mic", r"\btextil", r"\bmaquila"],
    "consumer_goods": [r"coca-?cola", r"\bpepsi", r"\bbimbo\b", r"\bnestl[eé]\b", r"\bunilever\b", r"\bp&g\b", r"procter", r"\bcolgate\b", r"\bkimberly\b", r"\bl'or[eé]al\b", r"\bdanone\b", r"\bmondelez\b", r"\bkellogg", r"\bherdez\b", r"\blala\b", r"\bjumex\b", r"\bheineken\b", r"\bmodelo\b", r"\bcuervo\b", r"\bdiageo\b", r"\bbacardi\b", r"\bconsumo\b"],
    "retail": [r"\bwalmart\b", r"\bliverpool\b", r"\bsoriana\b", r"\bchedraui\b", r"\boxxo\b", r"\bcoppel\b", r"\belektra\b", r"\bpalacio de hierro\b", r"\bsears\b", r"\bhome depot\b", r"\bcostco\b", r"\bretail\b", r"\btienda", r"\bfemsa\b"],
    "pharmaceutical": [r"\bfarmac", r"\bpharma", r"\blaboratorio", r"\bpfizer\b", r"\bbayer\b", r"\bnovartis\b", r"\broche\b", r"\bsanofi\b", r"\bgenomma\b", r"\bastrazeneca\b", r"\bmerck\b", r"\bbiotec"],
    "automotive": [r"\bautomotriz\b", r"\bautomotive\b", r"\bnissan\b", r"\btoyota\b", r"\bford\b", r"\bgeneral motors\b", r"\bvolkswagen\b", r"\bhonda\b", r"\bbmw\b", r"\bautopartes\b", r"\bstellantis\b", r"\bkia\b", r"\bmazda\b"],
    "logistics_supply_chain": [r"\blog[ií]stic", r"\bsupply chain\b", r"\bdhl\b", r"\bfedex\b", r"\bups\b", r"\bestafeta\b", r"\btransporte\b", r"\bfletes\b", r"\balmac[eé]n", r"\bdistribuci[oó]n\b"],
    "construction": [r"\bconstruc", r"\bcemex\b", r"\binmobiliar", r"\bdesarrollador", r"\bica\b", r"\bvivienda\b", r"\bedificaci"],
    "energy": [r"\bpemex\b", r"\bcfe\b", r"\benerg", r"\bpetr[oó]le", r"\bgas\b", r"\bsolar\b", r"\be[oó]lic", r"\biberdrola\b", r"\bshell\b"],
    "healthcare": [r"\bhospital", r"\bcl[ií]nica", r"\bsalud\b", r"\bm[eé]dic", r"\bhealth"],
    "food_beverage": [r"\balimentos\b", r"\bbebidas\b", r"\bfood\b", r"\brestauran", r"\bsigma\b", r"\bgruma\b", r"\bmaseca\b", r"\bbachoco\b", r"\bpilgrim"],
    "professional_services": [r"\bconsultor", r"\bconsulting\b", r"\bdeloitte\b", r"\bkpmg\b", r"\bpwc\b", r"\bey\b", r"\bernst", r"\bmckinsey\b", r"\bbcg\b", r"\baccenture\b", r"\bandersen\b", r"\bdespacho\b", r"\babogados\b", r"\bauditor"],
    "agriculture": [r"\bagr[ií]cola\b", r"\bagro", r"\bagricultura\b", r"\bsemillas\b", r"\bfertilizante", r"\bultraquimia\b", r"\bganader"],
    "hospitality": [r"\bhotel", r"\bturismo\b", r"\bresort", r"\bmarriott\b", r"\bhilton\b", r"\bposadas\b"],
    "education": [r"\buniversidad\b", r"\bescuela\b", r"\bcolegio\b", r"\btec de monterrey\b", r"\bitesm\b", r"\bunam\b", r"\beducaci[oó]n\b"],
    "media_entertainment": [r"\btelevisa\b", r"\btv azteca\b", r"\bmedios\b", r"\bentretenimiento\b", r"\bpublicidad\b", r"\bagencia\b"],
    "mining": [r"\bminer", r"\bmining\b", r"\bpe[nñ]oles\b", r"\bgrupo m[eé]xico\b"],
    "real_estate": [r"\bbienes ra[ií]ces\b", r"\breal estate\b", r"\bfibra\b"],
    "transportation": [r"\baerol[ií]nea", r"\baerom[eé]xico\b", r"\bvolaris\b", r"\bviva aerobus\b", r"\bferrocarril", r"\bautobuses\b", r"\bado\b"],
    "industrial_services": [r"\bservicios industriales\b", r"\bmantenimiento industrial\b"],
}
PRIORITY = ["telecommunications", "fintech", "technology", "financial_services", "pharmaceutical", "automotive", "consumer_goods", "retail",
            "food_beverage", "agriculture", "mining", "energy", "transportation", "logistics_supply_chain", "construction", "real_estate",
            "healthcare", "hospitality", "education", "media_entertainment", "professional_services", "manufacturing", "industrial_services"]


def infer_industry(pc):
    name = (pc.get("company_name") or "").lower()
    desc = (pc.get("description") or "").lower()
    for ind in PRIORITY:
        if any(re.search(k, name) for k in HEUR[ind]):
            return ind
    for ind in PRIORITY:
        if any(re.search(k, desc[:400]) for k in HEUR[ind][:6]):
            return ind
    return None


def enrich(cand):
    c = json.loads(json.dumps(cand, default=str))
    for pc in c.get("previous_companies") or []:
        pc["company_industry"] = infer_industry(pc)
    return c


def rescore(result, cand, job, weights):
    """Recalcula HMS con nueva IA, knockout de industria y pesos, reutilizando el resto del resultado v3."""
    comps = {k: dict(v) for k, v in result["component_breakdown"].items()}
    xi, ci, ev = industry_affinity(cand, job, NOW)
    comps["IA"].update({"raw": xi, "confidence": ci, "adjusted": ci * xi + (1 - ci) * SHRINKAGE_NEUTRAL, "evidence": ev})
    A = sum(weights[k] * comps[k]["adjusted"] for k in comps)
    G = math.exp(sum(weights[k] * math.log(comps[k]["adjusted"] + 0.01) for k in comps))
    B, P = result["boosts"]["total"], result["penalties"]["total"]
    core = max(0.0, min(1.0, 0.55 * A + 0.45 * G + B - P))
    K = result["knockout_results"]["K"]
    ko = industry_knockout(cand, job, NOW)
    if ko:
        K = K * ko["k_value"]
    hec = result["confidence_score"]
    hms = max(0, min(100, round(100 * K * core * (hec ** HEC_EXPONENT))))
    return hms, xi, ev, ko


def run_job(db, job, cands, label):
    pt = job.get("job_scorecard", {}).get("process_type") or "executive"
    weights = PROPOSED_WEIGHTS[pt]
    before, after = [], []
    for raw in cands:
        c = enrich(raw)
        r = score_v3(c, job)
        hms_new, xi, ev, ko = rescore(r, c, job, weights)
        base = {"id": c["id"], "name": c.get("full_name"), "title": c.get("current_title"), "company": c.get("current_company"),
                "industry": c.get("industry"), "area": c.get("functional_area"), "seniority": c.get("seniority")}
        before.append({**base, "hms": r["match_score_v3"], "ia": r["component_breakdown"]["IA"]["raw"]})
        after.append({**base, "hms": hms_new, "ia": xi, "target_years": ev.get("target_years"), "ko": ko["status"] if ko else None,
                      "evidence": "; ".join(f"{e['company']} ({e['industry']}, {e['years']}a)" for e in (ev.get("evidence") or [])[:3])})
    before.sort(key=lambda x: -x["hms"])
    after.sort(key=lambda x: -x["hms"])
    pos_b = {x["id"]: i + 1 for i, x in enumerate(before)}
    pos_a = {x["id"]: i + 1 for i, x in enumerate(after)}
    targets = job.get("job_scorecard", {}).get("target_industries") or [job.get("industry")]
    cov = coverage_by_industry([enrich(c) for c in cands], targets, NOW)
    print(f"\n{'=' * 100}\n{label} — {job['title']} ({job.get('company')}) | process={pt} | targets={targets} | requirement={job.get('job_scorecard', {}).get('industry_requirement')}")
    print(f"Cobertura (últimos 10 años, heurística): {cov}")
    print(f"\n  TOP 10 ANTES (v3 actual)")
    for i, x in enumerate(before[:10], 1):
        print(f"  {i:>2}. HMS {x['hms']:>3} IA {x['ia']:.2f} | {x['name']} — {x['title']} @ {x['company']} [{x['industry']}] → después #{pos_a[x['id']]}")
    print(f"\n  TOP 10 DESPUÉS (target_industries + IA trayectoria + knockout + pesos)")
    for i, x in enumerate(after[:10], 1):
        ko = f" KO:{x['ko']}" if x["ko"] and x["ko"] != "cumple" else ""
        print(f"  {i:>2}. HMS {x['hms']:>3} IA {x['ia']:.2f} ({x['target_years']}a) | {x['name']} — {x['title']} @ {x['company']} [{x['industry']}] ← antes #{pos_b[x['id']]}{ko} | {x['evidence']}")
    return {"job": job["title"], "process": pt, "targets": targets, "coverage": cov, "before": before[:30], "after": after[:30],
            "pos_before": pos_b, "pos_after": pos_a}


def main():
    db = get_db()
    cands = list(db.candidates.find({"is_deleted": {"$ne": True}}, {"_id": 0, "embedding": 0}))
    out = {}

    dc = db.jobs.find_one({"id": "a5a9ceb5-6a43-4547-bd30-7966a96959b5"}, {"_id": 0})
    dc["job_scorecard"]["target_industries"] = ["telecommunications", "technology", "fintech"]
    dc["job_scorecard"]["industry_requirement"] = "obligatoria"
    out["director_comercial"] = run_job(db, dc, cands, "DIRECTOR COMERCIAL")

    coo = db.jobs.find_one({"id": "f7dd7cf3-e710-4054-baf5-592c3340c3f9"}, {"_id": 0})
    coo.setdefault("job_scorecard", {})
    coo["job_scorecard"]["target_industries"] = [coo.get("industry")]
    coo["job_scorecard"]["industry_requirement"] = "preferente"
    res = run_job(db, coo, cands, "COO (contratado: Juan Manuel Herrera)")
    jm = "c17cd002-ab4a-4b1e-af7c-7db3b3989a18"
    print(f"\n  >> Juan Manuel Herrera Guerra: antes #{res['pos_before'].get(jm)} → después #{res['pos_after'].get(jm)}")
    out["coo"] = res

    fin = db.jobs.find_one({"id": "1745cda4-0080-45a2-b7d5-23ba1f347be3"}, {"_id": 0})
    fin.setdefault("job_scorecard", {})
    fin["job_scorecard"]["target_industries"] = [fin.get("industry")]
    fin["job_scorecard"]["industry_requirement"] = "preferente"
    res = run_job(db, fin, cands, "DIRECTOR DE FINANZAS (Gamaliel no debe subir)")
    gm = "89eaee03-666f-4f0c-a4d9-a658305374e0"
    print(f"\n  >> Gamaliel González Leines: antes #{res['pos_before'].get(gm)} → después #{res['pos_after'].get(gm)}")
    out["finanzas"] = res

    Path("/app/test_reports/phase2_simulation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
