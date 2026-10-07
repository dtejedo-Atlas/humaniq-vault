"""Fases 3 y 4: Afinar con IA (criterios sobre CV) + lista unificada v3+IA + cobertura + terna desde la lista."""
import os
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_refine_service import AIRefineService

# ---------- unify (unidad) ----------
v3 = [{"candidate_id": "a", "match_score_v3": 70}, {"candidate_id": "b", "match_score_v3": 60}, {"candidate_id": "c", "match_score_v3": 50}]
crit = [{"id": "k1", "text": "experiencia en telecom", "status": "done",
         "results": {"a": {"status": "no_cumple", "no_evidence": True}, "b": {"status": "parcial"},
                     "c": {"status": "cumple", "company": "AT&T", "period": "2018-2021"}}},
        {"id": "k2", "text": "pendiente", "status": "running", "results": {}}]
rows = AIRefineService.unify(v3, crit)
assert [r["candidate_id"] for r in rows] == ["c", "b", "a"], rows
assert rows[0]["moved_up_by"] == "subió por: experiencia en telecom en AT&T, 2018-2021" and rows[0]["v3_rank"] == 3
assert rows[2]["moved_up_by"] is None and "k2" not in rows[0]["ai_criteria"]
print("1. unify: orden criterios→HMS, 'subió por', criterios en curso no reordenan OK")

# ---------- API ----------
API = os.environ["API_URL"]
token = requests.post(f"{API}/api/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}, timeout=60).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
J = "a5a9ceb5-6a43-4547-bd30-7966a96959b5"

u = requests.get(f"{API}/api/jobs/{J}/unified-matches", headers=H, timeout=120).json()
assert u["results"] and u["results"][0]["rank"] == 1 and "v3_rank" in u["results"][0] and "ai_criteria" in u["results"][0]
assert u["coverage"]["targets"] == ["telecommunications", "technology", "fintech"] and u["coverage"]["per_industry"]["telecommunications"] > 0
print(f"2. unified-matches: {len(u['results'])} filas, cobertura {u['coverage']['per_industry']} OK")

crit_text = "que tenga experiencia en telecomunicaciones"   # ya evaluado antes → debe salir de caché
r = requests.post(f"{API}/api/jobs/{J}/ai-refine", headers=H, json={"criterion": crit_text, "scope": "top", "top_n": 30}, timeout=60).json()
assert r["status"] == "running" and r["criterion"]["total"] == 30 and r["estimate"]["estimated_cost_usd"] > 0
cid = r["criterion"]["id"]
for _ in range(60):
    st = requests.get(f"{API}/api/jobs/{J}/ai-refine/{cid}/status", headers=H, timeout=60).json()
    if st["status"] in ("done", "error"):
        break
    time.sleep(2)
assert st["status"] == "done" and st["evaluated"] == 30 and st["met"] > 0, st
print(f"3. ai-refine async: {st['met']} cumplen, {st['partial']} parcial, caché {st['from_cache']}/30, costo US${st['cost_usd']} OK")

u2 = requests.get(f"{API}/api/jobs/{J}/unified-matches", headers=H, timeout=120).json()
tags = [c for c in u2["criteria"] if c["id"] == cid]
assert len(tags) == 1 and len([c for c in u2["criteria"] if c["key"] == tags[0]["key"]]) == 1, "criterio duplicado"
top = u2["results"][0]
ev = top["ai_criteria"][cid]
assert ev["status"] in ("cumple", "parcial") and ev["quote"], ev
moved = [x for x in u2["results"] if x.get("moved_up_by")]
print(f"4. lista reordenada: #1 {top['candidate_name']} ({ev['status']}: \"{ev['quote'][:60]}…\"), {len(moved)} con 'subió por' OK")

sv = requests.post(f"{API}/api/jobs/{J}/ai-refine/{cid}/save-as-requirement", headers=H, json={"as_type": "skill"}, timeout=60).json()
assert any((s.get("skill") if isinstance(s, dict) else s) == crit_text for s in sv["scorecard"]["required_skills"])
sc = requests.get(f"{API}/api/jobs/{J}/scorecard", headers=H, timeout=60).json()["scorecard"]
sc["required_skills"] = [s for s in sc["required_skills"] if (s.get("skill") if isinstance(s, dict) else s) != crit_text]
requests.put(f"{API}/api/jobs/{J}/scorecard", headers=H, json=sc, timeout=60)
print("5. guardar criterio como skill del scorecard (y limpieza) OK")

d = requests.delete(f"{API}/api/jobs/{J}/ai-refine/{cid}", headers=H, timeout=60).json()
assert not any(c["id"] == cid for c in d["criteria"])
print("6. quitar etiqueta de criterio OK")

est = requests.get(f"{API}/api/jobs/{J}/ai-refine/estimate?scope=all", headers=H, timeout=60).json()
assert est["candidates"] > 500 and est["estimated_cost_usd"] > 1
print(f"7. estimación toda la base: {est['candidates']} CVs ≈ US${est['estimated_cost_usd']} ({est['estimated_minutes']} min) OK")

rev = requests.get(f"{API}/api/jobs/{J}/ai-match-review", headers=H, timeout=60)
if rev.status_code == 200 and rev.json().get("source") == "unified_v3_ai":
    ids_unified = [x["candidate_id"] for x in u2["results"][:5]]
    inside = sum(1 for s in rev.json()["shortlist"] if s["candidate_id"] in ids_unified)
    print(f"8. terna IA (source unified_v3_ai): {inside}/{len(rev.json()['shortlist'])} finalistas en el top 5 actual "
          f"({'OK' if inside == len(rev.json()['shortlist']) else 'análisis previo a cambios de criterios; regenerar desde la UI'})")
else:
    print("8. terna IA: sin análisis unificado guardado aún (se genera desde la UI)")
print("\nTODO OK")
