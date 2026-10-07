"""Fase 1: snapshot de matching por vacante + contacto/CV en resultados. Fase 2 (módulo): industria por trayectoria."""
import os
import sys
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from industry_trajectory import parse_date, industry_affinity, industry_knockout, trajectory_profile, coverage_by_industry

# ---------- Fase 2 (unidad, sin red) ----------
NOW = datetime(2026, 6, 1)
assert parse_date("08/2006") == datetime(2006, 8, 1) and parse_date("2019-03") == datetime(2019, 3, 1)
assert parse_date("Presente", NOW) == NOW and parse_date("mar 2019") == datetime(2019, 3, 1) and parse_date("2021") == datetime(2021, 1, 1)
print("1. parse_date MM/YYYY, YYYY-MM, mes texto, presente OK")

job = {"industry": "telecommunications", "job_scorecard": {"target_industries": ["telecommunications", "technology"], "industry_requirement": "obligatoria"}}
telco = {"industry": "telecommunications", "current_company": "AT&T", "previous_companies": [
    {"company_name": "AT&T", "start_date": "2018-01", "end_date": None, "company_industry": "telecommunications"},
    {"company_name": "Bimbo", "start_date": "2012-01", "end_date": "2017-12", "company_industry": "consumer_goods"}]}
cpg = {"industry": "consumer_goods", "current_company": "Coca-Cola", "previous_companies": [
    {"company_name": "Coca-Cola", "start_date": "2010-01", "end_date": None, "company_industry": "consumer_goods"}]}
xi_t, ci_t, ev_t = industry_affinity(telco, job, NOW)
xi_c, ci_c, ev_c = industry_affinity(cpg, job, NOW)
assert xi_t > 0.9 and ev_t["target_years"] >= 8 and ev_t["evidence"][0]["company"] == "AT&T", (xi_t, ev_t)
assert xi_c < 0.2 and ev_c["target_years"] == 0, (xi_c, ev_c)
assert industry_knockout(telco, job, NOW)["status"] == "cumple"
assert industry_knockout(cpg, job, NOW)["status"] == "no_cumple_importante"
assert industry_knockout(cpg, {**job, "job_scorecard": {**job["job_scorecard"], "industry_requirement": "preferente"}}, NOW) is None
print(f"2. IA trayectoria telco={xi_t} vs consumo={xi_c}; knockout obligatoria OK")

stale = {"industry": "fintech", "current_company": "FLINK", "previous_companies": [
    {"company_name": "Banamex", "start_date": "2012-03", "end_date": "2021-12", "company_industry": "financial_services"}]}
rows = trajectory_profile(stale, NOW)
assert any(r.get("assumed") and r["industry"] == "fintech" for r in rows)
cov = coverage_by_industry([telco, cpg, stale], ["telecommunications", "fintech"], NOW)
assert cov == {"per_industry": {"telecommunications": 1, "fintech": 1}, "any": 2}, cov
print("3. empleo actual asumido + cobertura por industria OK")

# ---------- Fase 1 (API) ----------
API = os.environ["API_URL"]
token = requests.post(f"{API}/api/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}, timeout=60).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
job_id = "a5a9ceb5-6a43-4547-bd30-7966a96959b5"

res = requests.post(f"{API}/api/jobs/{job_id}/match?threshold=50&limit=5", headers=H, timeout=180).json()
first = res["results"][0]
assert res.get("snapshot_at") and "email" in first and "has_cv" in first and "linkedin_url" in first, first.keys()
print("4. POST /match devuelve contacto (email/phone/linkedin/has_cv) y snapshot_at OK")

snap = requests.get(f"{API}/api/jobs/{job_id}/match-snapshot?engine=v2", headers=H, timeout=60).json()
assert snap["snapshot_at"] == res["snapshot_at"] and snap["results"][0]["candidate_id"] == first["candidate_id"]
print("5. GET /match-snapshot?engine=v2 regresa el último cálculo sin recalcular OK")

r404 = requests.get(f"{API}/api/jobs/no-existe/match-snapshot?engine=v3", headers=H, timeout=60)
assert r404.status_code == 404
print("6. snapshot inexistente → 404 OK")

cv = requests.get(f"{API}/api/candidates/{first['candidate_id']}/download-cv", headers=H, timeout=60)
assert cv.status_code == 200 and cv.headers.get("content-type", "").split(";")[0] in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword", "application/octet-stream"), cv.headers
print("7. download-cv entrega archivo para el visor OK", cv.headers.get("content-type"))
print("\nTODO OK")
