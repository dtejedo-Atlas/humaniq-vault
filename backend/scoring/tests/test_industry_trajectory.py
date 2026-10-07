"""Tests v3.1: IA por trayectoria, knockout de industria, pesos nuevos y compatibilidad."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scoring.engine_v3 import score_v3
from scoring.components import calculate_ia
from scoring.knockouts import evaluate_knockouts
from scoring.config_v3 import WEIGHTS_BY_PROCESS
from industry_trajectory import parse_date, trajectory_profile, industry_affinity

NOW = datetime(2026, 6, 1)

BASE = {"full_name": "X", "functional_area": "sales", "seniority": "director", "years_experience": 15,
        "skills": ["ventas", "negociación"], "current_title": "Director Comercial", "location": "CDMX"}
TELCO = {**BASE, "id": "t", "industry": "telecommunications", "current_company": "AT&T", "previous_companies": [
    {"company_name": "AT&T", "title": "Director Comercial", "start_date": "2018-01", "end_date": None, "company_industry": "telecommunications"},
    {"company_name": "Bimbo", "title": "Gerente", "start_date": "2012-01", "end_date": "2017-12", "company_industry": "consumer_goods"}]}
CPG = {**BASE, "id": "c", "industry": "consumer_goods", "current_company": "Coca-Cola", "previous_companies": [
    {"company_name": "Coca-Cola", "title": "Director Comercial", "start_date": "2010-01", "end_date": None, "company_industry": "consumer_goods"}]}
JOB = {"id": "j", "title": "Director Comercial", "industry": "telecommunications", "functional_area": "sales", "seniority": "director",
       "min_experience": 10, "required_skills": ["ventas"],
       "job_scorecard": {"process_type": "executive", "target_industries": ["telecommunications", "technology", "fintech"],
                         "industry_requirement": "obligatoria"}}


def test_weights_sum_to_one_and_dominant_components():
    for profile, w in WEIGHTS_BY_PROCESS.items():
        assert abs(sum(w.values()) - 1.0) < 1e-6, profile
        assert w["ER"] + w["FA"] + w["SA"] + w["IA"] >= 0.55, profile
    assert WEIGHTS_BY_PROCESS["executive"]["IA"] == 0.17
    assert WEIGHTS_BY_PROCESS["operational"]["SK"] == 0.22


def test_parse_date_formats():
    assert parse_date("08/2006") == datetime(2006, 8, 1)
    assert parse_date("2019-03") == datetime(2019, 3, 1)
    assert parse_date("mar 2019") == datetime(2019, 3, 1)
    assert parse_date("Presente", NOW) == NOW
    assert parse_date("basura") is None


def test_ia_trajectory_vs_transferability():
    xi_t, ci_t, ev_t = calculate_ia(TELCO, JOB)
    xi_c, ci_c, ev_c = calculate_ia(CPG, JOB)
    assert xi_t > 0.9 and ev_t["target_years"] >= 8 and ev_t["evidence"][0]["company"] == "AT&T"
    assert xi_c < 0.2 and ev_c["target_years"] == 0
    assert ev_t["job_industries"] == ["telecommunications", "technology", "fintech"]


def test_multiple_target_industries_count_previous_jobs():
    cand = {**BASE, "id": "m", "industry": "consumer_goods", "current_company": "Bimbo", "previous_companies": [
        {"company_name": "Bimbo", "start_date": "2023-01", "end_date": None, "company_industry": "consumer_goods"},
        {"company_name": "Clip", "start_date": "2017-01", "end_date": "2022-12", "company_industry": "fintech"}]}
    xi, ci, ev = calculate_ia(cand, JOB)
    assert 0.4 < xi < 0.8 and ev["target_years"] >= 5 and ev["evidence"][0]["industry"] == "fintech"


def test_no_invented_years_for_undated_current_job():
    stale = {**BASE, "id": "s", "industry": "fintech", "current_company": "FLINK", "previous_companies": [
        {"company_name": "Banamex", "start_date": "2012-03", "end_date": "2021-12", "company_industry": "financial_services"}]}
    rows = trajectory_profile(stale, NOW)
    undated = [r for r in rows if r.get("undated")]
    assert undated and undated[0]["years"] == 1.0 and undated[0]["start"] == "sin fecha"
    xi, ci, ev = industry_affinity(stale, {"industry": "fintech"}, NOW)
    assert ci <= 0.6 and ev["undated_current_job"] and ev["evidence"][0]["note"] == "sin fecha"
    dated = {**stale, "current_start_date": "2022-01"}
    rows = trajectory_profile(dated, NOW)
    assert not any(r.get("undated") for r in rows) and rows[-1]["years"] > 4


def test_industry_knockout_only_when_mandatory():
    K, results = evaluate_knockouts(CPG, JOB, JOB["job_scorecard"])
    ind = next(r for r in results if r["criterion"] == "industry")
    assert ind["status"] == "no_cumple_importante" and K <= 0.5
    K2, results2 = evaluate_knockouts(TELCO, JOB, JOB["job_scorecard"])
    assert next(r for r in results2 if r["criterion"] == "industry")["status"] == "cumple"
    soft = {**JOB, "job_scorecard": {**JOB["job_scorecard"], "industry_requirement": "preferente"}}
    _, results3 = evaluate_knockouts(CPG, soft, soft["job_scorecard"])
    assert next(r for r in results3 if r["criterion"] == "industry")["status"] == "no_aplica"


def test_score_v3_ranks_target_industry_first_and_legacy_compat():
    r_t, r_c = score_v3(TELCO, JOB), score_v3(CPG, JOB)
    assert r_t["match_score_v3"] > r_c["match_score_v3"] + 15
    assert r_t["weights_used"]["IA"] == 0.17
    legacy = {k: v for k, v in JOB.items() if k != "job_scorecard"}
    legacy["job_scorecard"] = {"process_type": "executive"}
    r_legacy = score_v3(TELCO, legacy)
    assert r_legacy["component_breakdown"]["IA"]["evidence"]["job_industries"] == ["telecommunications"]
    assert r_legacy["match_score_v3"] >= r_t["match_score_v3"] - 3


def test_indifferent_requirement_does_not_discriminate():
    job = {**JOB, "job_scorecard": {**JOB["job_scorecard"], "industry_requirement": "indiferente"}}
    assert calculate_ia(TELCO, job)[0] == calculate_ia(CPG, job)[0]
