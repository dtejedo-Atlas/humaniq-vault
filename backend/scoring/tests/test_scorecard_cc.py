"""
Tests para Fase 4: WEIGHTS_BY_PROCESS, componente CC y scorecard.
"""
import sys
import pytest

sys.path.insert(0, '/app/backend')

from scoring.config_v3 import WEIGHTS_BY_PROCESS, DEFAULT_PROCESS
from scoring.components import calculate_cc, CALIBER_INDEX
from scoring.engine_v3 import score_v3, derive_default_scorecard


CANDIDATE_MULTI = {
    "id": "c1",
    "full_name": "Candidato Multinacional",
    "email": "multi@test.com",
    "phone": "5551234567",
    "current_title": "Director Comercial",
    "years_experience": 15,
    "skills": ["ventas", "negociación", "estrategia comercial"],
    "languages": ["español", "inglés"],
    "functional_area": "sales",
    "seniority": "director",
    "industry": "consumer_goods",
    "previous_companies": [
        {"company_name": "Nestlé", "title": "Director Comercial", "start_date": "2018-01-01", "end_date": None, "company_caliber": "multinacional_global"},
        {"company_name": "Bimbo", "title": "Gerente de Ventas", "start_date": "2013-01-01", "end_date": "2017-12-31", "company_caliber": "corporativo_nacional"},
    ],
}

CANDIDATE_NO_CALIBER = {
    "id": "c2",
    "full_name": "Candidato Sin Calibre",
    "previous_companies": [
        {"company_name": "Empresa X", "title": "Gerente", "start_date": "2019-01-01"},
        {"company_name": "Empresa Y", "title": "Analista", "start_date": "2015-01-01"},
    ],
}

JOB_BASE = {
    "id": "j1",
    "title": "Director Comercial",
    "industry": "consumer_goods",
    "functional_area": "sales",
    "seniority": "director",
    "min_experience": 8,
}


class TestWeightsByProcess:
    """Tests para los 4 perfiles de pesos"""

    def test_each_profile_sums_to_one(self):
        for profile, weights in WEIGHTS_BY_PROCESS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"'{profile}' suma {total}, esperado 1.0"

    def test_each_profile_has_11_components(self):
        expected = {"SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ", "CC"}
        for profile, weights in WEIGHTS_BY_PROCESS.items():
            assert set(weights.keys()) == expected, f"'{profile}' tiene componentes incorrectos"

    def test_four_profiles_exist(self):
        assert set(WEIGHTS_BY_PROCESS.keys()) == {"c_level", "executive", "managerial", "operational"}

    def test_default_process_valid(self):
        assert DEFAULT_PROCESS in WEIGHTS_BY_PROCESS


class TestCompanyCaliber:
    """Tests para el componente CC"""

    def test_cc_multinacional_vs_multinacional_target(self):
        scorecard = {"target_company_caliber": "multinacional_global"}
        xi, ci, ev = calculate_cc(CANDIDATE_MULTI, JOB_BASE, scorecard)
        assert xi == 1.0, f"xi={xi}, esperado 1.0 (distancia 0)"
        assert ci == 1.0, f"ci={ci}, esperado 1.0 (todas con calibre)"
        assert ev["candidate_caliber"] == "multinacional_global"

    def test_cc_multinacional_vs_pyme_target_penaliza_sobrecalibre(self):
        scorecard = {"target_company_caliber": "pyme"}
        xi, ci, ev = calculate_cc(CANDIDATE_MULTI, JOB_BASE, scorecard)
        # distancia |4-1|=3 → xi = 1 - 3/4 = 0.25
        assert xi == 0.25, f"xi={xi}, esperado 0.25 (sobre-calibre penaliza)"
        assert xi < 0.5, "Sobre-calibre debe quedar por debajo del neutral"

    def test_cc_target_none_es_neutral(self):
        scorecard = {"target_company_caliber": None}
        xi, ci, ev = calculate_cc(CANDIDATE_MULTI, JOB_BASE, scorecard)
        assert xi == 0.5
        assert ci == 0.0

    def test_cc_sin_scorecard_es_neutral(self):
        xi, ci, ev = calculate_cc(CANDIDATE_MULTI, JOB_BASE, None)
        assert xi == 0.5
        assert ci == 0.0

    def test_cc_candidato_sin_calibre_es_neutral(self):
        scorecard = {"target_company_caliber": "mediana"}
        xi, ci, ev = calculate_cc(CANDIDATE_NO_CALIBER, JOB_BASE, scorecard)
        assert xi == 0.5
        assert ci == 0.0
        assert ev["candidate_caliber"] is None

    def test_cc_ci_proporcion_empresas_con_calibre(self):
        candidate = {
            "previous_companies": [
                {"company_name": "A", "title": "X", "company_caliber": "mediana"},
                {"company_name": "B", "title": "Y"},
                {"company_name": "C", "title": "Z"},
                {"company_name": "D", "title": "W"},
            ]
        }
        scorecard = {"target_company_caliber": "mediana"}
        xi, ci, ev = calculate_cc(candidate, JOB_BASE, scorecard)
        assert ci == 0.25, f"ci={ci}, esperado 0.25 (1 de 4 con calibre)"
        assert xi == 1.0

    def test_caliber_index_ordinal(self):
        assert CALIBER_INDEX["startup"] == 0
        assert CALIBER_INDEX["pyme"] == 1
        assert CALIBER_INDEX["mediana"] == 2
        assert CALIBER_INDEX["corporativo_nacional"] == 3
        assert CALIBER_INDEX["multinacional_global"] == 4


class TestProcessTypeInEngine:
    """Tests para pesos por process_type integrados en score_v3"""

    def test_c_level_weights_favor_cc_er_over_sk(self):
        scorecard = {"process_type": "c_level", "target_company_caliber": "multinacional_global"}
        result = score_v3(CANDIDATE_MULTI, JOB_BASE, scorecard)
        w = result["weights_used"]
        assert result["process_type"] == "c_level"
        assert w["CC"] > w["SK"], "c_level: CC debe pesar más que SK"
        assert w["ER"] > w["SK"], "c_level: ER debe pesar más que SK"

    def test_operational_weights_favor_sk_over_cc(self):
        scorecard = {"process_type": "operational"}
        result = score_v3(CANDIDATE_MULTI, JOB_BASE, scorecard)
        w = result["weights_used"]
        assert result["process_type"] == "operational"
        assert w["SK"] > w["CC"], "operational: SK debe pesar más que CC"
        assert w["SK"] == 0.24

    def test_cc_in_component_breakdown(self):
        scorecard = {"process_type": "executive", "target_company_caliber": "corporativo_nacional"}
        result = score_v3(CANDIDATE_MULTI, JOB_BASE, scorecard)
        assert "CC" in result["component_breakdown"]
        assert len(result["component_breakdown"]) == 11

    def test_invalid_process_type_falls_back_to_default(self):
        scorecard = {"process_type": "inexistente"}
        result = score_v3(CANDIDATE_MULTI, JOB_BASE, scorecard)
        assert result["process_type"] == DEFAULT_PROCESS

    def test_score_uses_saved_scorecard_from_job(self):
        job = dict(JOB_BASE)
        job["job_scorecard"] = {"process_type": "c_level", "target_company_caliber": "multinacional_global"}
        result = score_v3(CANDIDATE_MULTI, job)
        assert result["process_type"] == "c_level"


class TestDeriveDefaultScorecard:
    """Tests para la derivación de scorecard por seniority"""

    @pytest.mark.parametrize("seniority,expected", [
        ("c_level", "c_level"),
        ("vp", "c_level"),
        ("director", "executive"),
        ("manager", "managerial"),
        ("senior", "operational"),
        ("junior", "operational"),
        (None, "operational"),
    ])
    def test_process_type_from_seniority(self, seniority, expected):
        job = dict(JOB_BASE)
        job["seniority"] = seniority
        sc = derive_default_scorecard(job)
        assert sc["process_type"] == expected

    def test_languages_derived_from_job(self):
        job = dict(JOB_BASE)
        job["language_requirements"] = ["english:advanced"]
        sc = derive_default_scorecard(job)
        assert sc["required_languages"] == ["english:advanced"]
        assert sc["non_negotiables"] == []
        assert sc["target_company_caliber"] is None
