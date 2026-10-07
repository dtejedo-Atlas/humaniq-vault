"""Reporte post-aplicación Fase 2: top 10 con evidencia de industria + distribución de acciones (3 vacantes)."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import get_db  # noqa: E402
from scoring.engine_v3 import score_v3  # noqa: E402

JOBS = {
    "Director Comercial (Diri Telecom)": "a5a9ceb5-6a43-4547-bd30-7966a96959b5",
    "COO (Ultraquimia)": "f7dd7cf3-e710-4054-baf5-592c3340c3f9",
    "Director de Finanzas (fintech)": "1745cda4-0080-45a2-b7d5-23ba1f347be3",
}
WATCH = {"Juan Manuel Herrera Guerra": "c17cd002-ab4a-4b1e-af7c-7db3b3989a18", "Gamaliel González Leines": "89eaee03-666f-4f0c-a4d9-a658305374e0"}
ACTION_ES = {"advance_to_screening": "Entrevistar", "review_manually": "Revisar", "possible_backup": "Backup",
             "low_priority": "Prioridad baja", "save_for_other_role": "Guardar otro rol", "do_not_advance_knockout": "No avanzar (KO)"}


def main():
    db = get_db()
    cands = list(db.candidates.find({"is_deleted": {"$ne": True}}, {"_id": 0, "embedding": 0}))
    with_ind = sum(1 for c in cands for p in (c.get("previous_companies") or []) if p.get("company_industry"))
    total_pc = sum(len(c.get("previous_companies") or []) for c in cands)
    print(f"Backfill company_industry: {with_ind}/{total_pc} empleos con industria ({total_pc - with_ind} null)\n")
    out = {}
    for label, jid in JOBS.items():
        job = db.jobs.find_one({"id": jid}, {"_id": 0})
        sc = job.get("job_scorecard") or {}
        rows = []
        for c in cands:
            r = score_v3(c, job)
            rows.append((r["match_score_v3"], r["recommended_action"], c, r))
        rows.sort(key=lambda x: -x[0])
        dist = Counter(ACTION_ES.get(a, a) for _, a, _, _ in rows)
        dist_top50 = Counter(ACTION_ES.get(a, a) for _, a, _, _ in rows[:50])
        print("=" * 110)
        print(f"{label} | targets={sc.get('target_industries') or [job.get('industry')]} req={sc.get('industry_requirement', 'preferente')} | process={sc.get('process_type')}")
        print(f"Distribución de acciones (617): {dict(dist)}")
        print(f"Distribución top 50: {dict(dist_top50)} | HMS máx {rows[0][0]}, #10 {rows[9][0]}, #50 {rows[49][0]}")
        print("TOP 10:")
        for i, (hms, act, c, r) in enumerate(rows[:10], 1):
            ia = r["component_breakdown"]["IA"]
            ev = ia.get("evidence") or {}
            evs = "; ".join(f"{e.get('company')} [{e.get('industry')}] {e.get('years')}a{' (sin fecha)' if e.get('note') else ''}" for e in (ev.get("evidence") or [])[:3]) or "—"
            ko = r["knockout_results"].get("summary", {})
            print(f"  {i:>2}. HMS {hms:>3} {ACTION_ES.get(act, act):<15} IA {ia['raw']:.2f} ci {ia['confidence']:.2f} ({ev.get('target_years', 0)}a) | {c.get('full_name')} — {c.get('current_title')} @ {c.get('current_company')} [{c.get('industry')}/{c.get('seniority')}] | {evs}")
        pos = {cid: i + 1 for i, (_, _, c, _) in enumerate(rows) for cid in [c["id"]]}
        for name, cid in WATCH.items():
            if cid in pos:
                print(f"  >> {name}: #{pos[cid]} (HMS {rows[pos[cid]-1][0]})")
        out[label] = {"distribution": dict(dist), "top50": dict(dist_top50),
                      "top10": [{"hms": h, "action": a, "name": c.get("full_name"), "company": c.get("current_company"),
                                 "ia": r["component_breakdown"]["IA"]["raw"], "evidence": (r["component_breakdown"]["IA"].get("evidence") or {}).get("evidence")}
                                for h, a, c, r in rows[:10]]}
    Path("/app/test_reports/phase2_applied_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
