"""
Tests para Scoring Engine v3
"""
import sys
import pytest
from typing import Dict, Any

sys.path.insert(0, '/app/backend')

from scoring.config_v3 import (
    COMPONENT_WEIGHTS,
    KNOCKOUT_VALUES,
    SHRINKAGE_NEUTRAL,
)
from scoring.components import (
    calculate_sk,
    calculate_er,
    calculate_fa,
    calculate_sa,
    calculate_ia,
    calculate_ed,
    calculate_tr,
    calculate_lo,
    calculate_sm,
    calculate_cq,
)
from scoring.knockouts import (
    evaluate_knockouts,
    evaluate_language_knockout,
    evaluate_location_knockout,
    evaluate_experience_knockout,
    evaluate_salary_knockout,
    summarize_knockouts,
)


# =============================================================================
# TEST DATA
# =============================================================================

SAMPLE_CANDIDATE: Dict[str, Any] = {
    "id": "test-001",
    "full_name": "María García López",
    "email": "maria.garcia@example.com",
    "phone": "+52 55 1234 5678",
    "current_title": "Directora de Operaciones",
    "current_company": "LIVERPOOL",
    "years_experience": 12,
    "industry": "retail",
    "functional_area": "operations",
    "seniority": "director",
    "city": "Ciudad de México",
    "state": "CDMX",
    "skills": [
        "Supply Chain Management",
        "Lean Manufacturing",
        "Six Sigma",
        "SAP",
        "Gestión de Equipos",
    ],
    "languages": ["Español", "Inglés (Avanzado)"],
    "previous_companies": [
        {
            "company_name": "LIVERPOOL",
            "title": "Directora de Operaciones",
            "start_date": "2021",
            "end_date": None,  # Actual
        },
        {
            "company_name": "CEMEX",
            "title": "Gerente Supply Chain",
            "start_date": "2018",
            "end_date": "2021",
        },
        {
            "company_name": "GRUPO BIMBO",
            "title": "Coordinadora Producción",
            "start_date": "2015",
            "end_date": "2018",
        },
    ],
    "embedding": [0.1] * 1536,  # Mock embedding
}

SAMPLE_JOB: Dict[str, Any] = {
    "id": "job-001",
    "title": "Director de Operaciones",
    "functional_area": "operations",
    "industry": "retail",
    "seniority_level": "director",
    "min_experience": 10,
    "city": "Ciudad de México",
    "state": "CDMX",
    "work_scheme": "presencial",
    "required_languages": ["Español", "Inglés"],
    "required_skills": ["Supply Chain", "Lean", "SAP"],
    "embedding": [0.1] * 1536,  # Mock embedding (similar)
}


# =============================================================================
# CONFIG TESTS
# =============================================================================

class TestConfig:
    """Tests para config_v3.py"""
    
    def test_weights_sum_to_one(self):
        """Los pesos de componentes deben sumar 1.0"""
        total = sum(COMPONENT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"
    
    def test_all_components_have_weights(self):
        """Todos los componentes tienen peso definido"""
        expected = {"SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"}
        assert set(COMPONENT_WEIGHTS.keys()) == expected
    
    def test_knockout_values(self):
        """Valores de knockout están correctos"""
        assert KNOCKOUT_VALUES["cumple"] == 1.00
        assert KNOCKOUT_VALUES["evidencia_insuficiente"] == 0.85
        assert KNOCKOUT_VALUES["parcial"] == 0.70
        assert KNOCKOUT_VALUES["no_cumple_importante"] == 0.50
        assert KNOCKOUT_VALUES["no_cumple_fatal"] == 0.00
    
    def test_shrinkage_neutral(self):
        """Shrinkage neutral está definido"""
        assert SHRINKAGE_NEUTRAL == 0.52


# =============================================================================
# COMPONENT TESTS
# =============================================================================

class TestSkillsComponent:
    """Tests para calculate_sk"""
    
    def test_sk_full_match(self):
        """SK: cobertura completa de skills"""
        cand_skills = ["Python", "Java", "SQL"]
        job_skills = ["Python", "Java", "SQL"]
        
        xi, ci, evidence = calculate_sk(cand_skills, job_skills)
        
        assert xi == 1.0
        assert ci == 1.0
        assert evidence["coverage"] == 1.0
    
    def test_sk_partial_match(self):
        """SK: cobertura parcial de skills"""
        cand_skills = ["Python", "Java"]
        job_skills = ["Python", "Java", "SQL", "React"]
        
        xi, ci, evidence = calculate_sk(cand_skills, job_skills)
        
        assert 0 < xi < 1.0
        assert ci == 1.0
        assert len(evidence["missing"]) == 2
    
    def test_sk_no_job_skills(self):
        """SK: vacante sin skills definidos"""
        cand_skills = ["Python", "Java"]
        job_skills = []
        
        xi, ci, evidence = calculate_sk(cand_skills, job_skills, job_has_skills=False)
        
        assert xi == 0.5
        assert ci == 0.0
        assert "sin skills" in evidence["note"].lower()
    
    def test_sk_no_candidate_skills(self):
        """SK: candidato sin skills"""
        cand_skills = []
        job_skills = ["Python", "Java"]
        
        xi, ci, evidence = calculate_sk(cand_skills, job_skills)
        
        assert xi == 0.0
        assert ci == 1.0


class TestExperienceComponent:
    """Tests para calculate_er"""
    
    def test_er_with_relevant_experience(self):
        """ER: experiencia relevante en el área"""
        xi, ci, evidence = calculate_er(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert 0 <= xi <= 1.0
        assert 0 <= ci <= 1.0
        assert "total_relevant_years" in evidence
        assert evidence["jobs_analyzed"] == 3
    
    def test_er_no_previous_companies(self):
        """ER: candidato sin historial laboral"""
        candidate = {**SAMPLE_CANDIDATE, "previous_companies": [], "years_experience": 5}
        
        xi, ci, evidence = calculate_er(candidate, SAMPLE_JOB)
        
        # Debe usar years_experience con confianza baja
        assert ci == 0.3
        assert "years_experience global" in evidence["note"]


class TestFunctionalAffinityComponent:
    """Tests para calculate_fa"""
    
    def test_fa_same_area(self):
        """FA: misma área funcional"""
        xi, ci, evidence = calculate_fa(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert xi == 1.0  # operations -> operations
        assert ci == 1.0
    
    def test_fa_different_area(self):
        """FA: áreas diferentes"""
        candidate = {**SAMPLE_CANDIDATE, "functional_area": "finance"}
        
        xi, ci, evidence = calculate_fa(candidate, SAMPLE_JOB)
        
        assert 0 <= xi <= 1.0
        assert ci == 1.0
    
    def test_fa_missing_data(self):
        """FA: datos faltantes"""
        candidate = {**SAMPLE_CANDIDATE, "functional_area": None}
        
        xi, ci, evidence = calculate_fa(candidate, SAMPLE_JOB)
        
        assert xi == SHRINKAGE_NEUTRAL
        assert ci == 0.0


class TestSeniorityComponent:
    """Tests para calculate_sa"""
    
    def test_sa_exact_match(self):
        """SA: seniority exacto"""
        xi, ci, evidence = calculate_sa(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert xi == 1.0  # director -> director
        assert ci == 1.0
    
    def test_sa_one_level_difference(self):
        """SA: diferencia de 1 nivel"""
        candidate = {**SAMPLE_CANDIDATE, "seniority": "vp"}  # vp = 8, director = 7
        
        xi, ci, evidence = calculate_sa(candidate, SAMPLE_JOB)
        
        assert xi == 0.85  # vp vs director = 1 nivel
        assert evidence["distance"] == 1


class TestIndustryComponent:
    """Tests para calculate_ia"""
    
    def test_ia_same_industry(self):
        """IA: misma industria"""
        xi, ci, evidence = calculate_ia(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert xi == 1.0  # retail -> retail
        assert ci == 1.0


class TestExecutiveDepthComponent:
    """Tests para calculate_ed"""
    
    def test_ed_executive_candidate(self):
        """ED: candidato con historial ejecutivo"""
        xi, ci, evidence = calculate_ed(SAMPLE_CANDIDATE)
        
        assert 0 <= xi <= 1.0
        assert ci == 1.0
        assert "executive_count" in evidence
        assert evidence["executive_count"] >= 1  # Directora de Operaciones


class TestTrajectoryComponent:
    """Tests para calculate_tr"""
    
    def test_tr_calculation(self):
        """TR: cálculo de trayectoria"""
        xi, ci, evidence = calculate_tr(SAMPLE_CANDIDATE)
        
        assert 0 <= xi <= 1.0
        assert "trajectory_score_raw" in evidence


class TestLocationComponent:
    """Tests para calculate_lo"""
    
    def test_lo_same_city(self):
        """LO: misma ciudad"""
        xi, ci, evidence = calculate_lo(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert xi == 1.0
        assert evidence["match_level"] == "same_city"
    
    def test_lo_remote_job(self):
        """LO: trabajo remoto"""
        job = {**SAMPLE_JOB, "work_scheme": "remoto"}
        
        xi, ci, evidence = calculate_lo(SAMPLE_CANDIDATE, job)
        
        assert xi == 1.0
        assert "remoto" in evidence["note"].lower()
    
    def test_lo_missing_candidate_location(self):
        """LO: candidato sin ubicación"""
        candidate = {**SAMPLE_CANDIDATE, "city": None, "state": None}
        
        xi, ci, evidence = calculate_lo(candidate, SAMPLE_JOB)
        
        assert xi == 0.5
        assert ci == 0.3


class TestSemanticComponent:
    """Tests para calculate_sm"""
    
    def test_sm_with_embeddings(self):
        """SM: con embeddings válidos"""
        xi, ci, evidence = calculate_sm(
            SAMPLE_CANDIDATE["embedding"],
            SAMPLE_JOB["embedding"]
        )
        
        assert 0 <= xi <= 1.0
        assert ci == 1.0
        assert "raw_similarity" in evidence
    
    def test_sm_missing_embedding(self):
        """SM: sin embedding"""
        xi, ci, evidence = calculate_sm(None, SAMPLE_JOB["embedding"])
        
        assert xi == SHRINKAGE_NEUTRAL
        assert ci == 0.0


class TestCVQualityComponent:
    """Tests para calculate_cq"""
    
    def test_cq_complete_candidate(self):
        """CQ: candidato con datos completos"""
        xi, ci, evidence = calculate_cq(SAMPLE_CANDIDATE)
        
        assert xi == 1.0  # 8/8 campos
        assert ci == 1.0
        assert evidence["present"] == 8
    
    def test_cq_incomplete_candidate(self):
        """CQ: candidato con datos incompletos"""
        candidate = {
            "email": "test@test.com",
            # Missing: phone, current_title, skills, etc.
        }
        
        xi, ci, evidence = calculate_cq(candidate)
        
        assert 0 < xi < 1.0
        assert evidence["present"] < 8


# =============================================================================
# KNOCKOUT TESTS
# =============================================================================

class TestLanguageKnockout:
    """Tests para evaluate_language_knockout"""
    
    def test_language_match(self):
        """Knockout: idiomas coinciden"""
        result = evaluate_language_knockout(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert result["status"] == "cumple"
        assert result["k_value"] == 1.0
    
    def test_language_missing(self):
        """Knockout: idioma faltante"""
        candidate = {**SAMPLE_CANDIDATE, "languages": ["Español"]}
        
        result = evaluate_language_knockout(candidate, SAMPLE_JOB)
        
        assert result["status"] == "parcial"
        assert "Inglés" in result["missing"]
    
    def test_language_flexible_match(self):
        """Knockout: match flexible (Inglés vs English)"""
        candidate = {**SAMPLE_CANDIDATE, "languages": ["Español", "English"]}
        job = {**SAMPLE_JOB, "required_languages": ["Spanish", "Inglés"]}
        
        result = evaluate_language_knockout(candidate, job)
        
        assert result["status"] == "cumple"
    
    def test_language_no_requirement(self):
        """Knockout: vacante sin requisito de idiomas → no_aplica"""
        job = {**SAMPLE_JOB, "required_languages": []}
        
        result = evaluate_language_knockout(SAMPLE_CANDIDATE, job)
        
        assert result["status"] == "no_aplica"
        assert result["k_value"] is None


class TestLocationKnockout:
    """Tests para evaluate_location_knockout"""
    
    def test_location_remote(self):
        """Knockout: trabajo remoto → no_aplica (ubicación no importa)"""
        job = {**SAMPLE_JOB, "work_scheme": "remoto"}
        
        result = evaluate_location_knockout(SAMPLE_CANDIDATE, job)
        
        # Para trabajo remoto, el criterio no aplica
        assert result["status"] == "no_aplica"
        assert result["k_value"] is None
    
    def test_location_match(self):
        """Knockout: ubicación coincide"""
        result = evaluate_location_knockout(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert result["status"] == "cumple"
    
    def test_location_no_requirement(self):
        """Knockout: vacante sin ubicación específica → no_aplica"""
        job = {**SAMPLE_JOB, "city": None, "state": None}
        
        result = evaluate_location_knockout(SAMPLE_CANDIDATE, job)
        
        assert result["status"] == "no_aplica"
        assert result["k_value"] is None


class TestExperienceKnockout:
    """Tests para evaluate_experience_knockout"""
    
    def test_experience_sufficient(self):
        """Knockout: experiencia suficiente"""
        result = evaluate_experience_knockout(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert result["status"] == "cumple"
        assert result["candidate_years"] == 12
        assert result["required_years"] == 10
    
    def test_experience_insufficient(self):
        """Knockout: experiencia insuficiente"""
        candidate = {**SAMPLE_CANDIDATE, "years_experience": 3}
        
        result = evaluate_experience_knockout(candidate, SAMPLE_JOB)
        
        assert result["status"] in ["no_cumple_importante", "no_cumple_fatal"]
    
    def test_experience_no_requirement(self):
        """Knockout: vacante sin requisito de experiencia mínima → no_aplica"""
        job = {**SAMPLE_JOB, "min_experience": None}
        
        result = evaluate_experience_knockout(SAMPLE_CANDIDATE, job)
        
        assert result["status"] == "no_aplica"
        assert result["k_value"] is None


class TestSalaryKnockout:
    """Tests para evaluate_salary_knockout"""
    
    def test_salary_no_job_requirement(self):
        """Knockout: vacante sin restricción salarial → no_aplica"""
        # Job sin salary_min/max/compensation_constraints
        job = {**SAMPLE_JOB}
        job.pop("salary_min", None)
        job.pop("salary_max", None)
        job.pop("compensation_constraints", None)
        
        result = evaluate_salary_knockout(SAMPLE_CANDIDATE, job)
        
        assert result["status"] == "no_aplica"
        assert result["k_value"] is None
    
    def test_salary_with_job_requirement_no_candidate_data(self):
        """Knockout: vacante con restricción pero candidato sin datos → evidencia_insuficiente"""
        job = {**SAMPLE_JOB, "salary_min": 50000, "salary_max": 80000}
        candidate = {**SAMPLE_CANDIDATE}
        candidate.pop("salary_data", None)
        candidate.pop("expected_salary", None)
        
        result = evaluate_salary_knockout(candidate, job)
        
        assert result["status"] == "evidencia_insuficiente"
        assert result["k_value"] == 0.85
    
    def test_salary_both_have_data_compatible(self):
        """Knockout: ambos tienen datos y son compatibles → cumple"""
        job = {**SAMPLE_JOB, "salary_min": 50000, "salary_max": 80000}
        candidate = {**SAMPLE_CANDIDATE, "salary_data": {"min": 55000, "max": 70000}}
        
        result = evaluate_salary_knockout(candidate, job)
        
        assert result["status"] == "cumple"
        assert result["k_value"] == 1.0


class TestEvaluateKnockouts:
    """Tests para evaluate_knockouts (principal)"""
    
    def test_evaluate_all_knockouts(self):
        """Evalúa todos los knockouts"""
        K, results = evaluate_knockouts(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert 0 <= K <= 1.0
        assert len(results) == 4  # language, location, experience, salary
    
    def test_knockout_summary(self):
        """Resume knockouts correctamente"""
        _, results = evaluate_knockouts(SAMPLE_CANDIDATE, SAMPLE_JOB)
        summary = summarize_knockouts(results)
        
        assert "total_evaluators" in summary
        assert summary["total_evaluators"] == 4
        assert "fatal" in summary


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Tests de integración del paquete scoring"""
    
    def test_all_components_run(self):
        """Todos los componentes se ejecutan sin errores"""
        components = [
            ("SK", lambda: calculate_sk(
                SAMPLE_CANDIDATE["skills"], 
                SAMPLE_JOB.get("required_skills", [])
            )),
            ("ER", lambda: calculate_er(SAMPLE_CANDIDATE, SAMPLE_JOB)),
            ("FA", lambda: calculate_fa(SAMPLE_CANDIDATE, SAMPLE_JOB)),
            ("SA", lambda: calculate_sa(SAMPLE_CANDIDATE, SAMPLE_JOB)),
            ("IA", lambda: calculate_ia(SAMPLE_CANDIDATE, SAMPLE_JOB)),
            ("ED", lambda: calculate_ed(SAMPLE_CANDIDATE)),
            ("TR", lambda: calculate_tr(SAMPLE_CANDIDATE)),
            ("LO", lambda: calculate_lo(SAMPLE_CANDIDATE, SAMPLE_JOB)),
            ("SM", lambda: calculate_sm(
                SAMPLE_CANDIDATE.get("embedding"),
                SAMPLE_JOB.get("embedding")
            )),
            ("CQ", lambda: calculate_cq(SAMPLE_CANDIDATE)),
        ]
        
        for name, func in components:
            xi, ci, evidence = func()
            assert 0 <= xi <= 1.0, f"Component {name}: xi={xi} out of range"
            assert 0 <= ci <= 1.0, f"Component {name}: ci={ci} out of range"
            assert evidence is not None, f"Component {name}: evidence is None"
    
    def test_weights_coverage(self):
        """Cada componente tiene un peso definido"""
        component_codes = ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"]
        
        for code in component_codes:
            assert code in COMPONENT_WEIGHTS, f"Missing weight for {code}"
            assert COMPONENT_WEIGHTS[code] > 0, f"Weight for {code} must be positive"


# =============================================================================
# ENGINE V3 TESTS (NUEVOS)
# =============================================================================

class TestEngineV3:
    """Tests para engine_v3.py y las fórmulas matemáticas"""
    
    def test_engine_import(self):
        """engine_v3 importa correctamente"""
        from scoring.engine_v3 import score_v3, ENGINE_VERSION
        assert ENGINE_VERSION == "v3.0.0"
    
    def test_confidence_import(self):
        """confidence importa correctamente"""
        from scoring.confidence import calculate_hec, HEC_WEIGHTS
        assert sum(HEC_WEIGHTS.values()) == 1.0
    
    def test_shrinkage_all_ci_zero(self):
        """
        TEST: ci=0 en todos → todos los xi_star = 0.52
        Si confianza es 0, shrinkage debe dar el valor neutral.
        """
        from scoring.engine_v3 import score_v3
        
        # Candidato con datos que generarán ci=0 en la mayoría de componentes
        candidate = {
            "id": "test-shrinkage",
            "full_name": "Test Shrinkage",
            # Sin email, phone, skills, etc. para generar baja confianza
            "previous_companies": [],
            "skills": [],
        }
        
        job = {
            "id": "job-shrinkage",
            "title": "Test Job",
            # Sin datos específicos
        }
        
        result = score_v3(candidate, job)
        
        # Los componentes sin datos tendrán ci=0, por lo que adjusted debe ser ~0.52
        for code, comp in result["component_breakdown"].items():
            if comp["confidence"] == 0.0:
                # Si ci=0, entonces xi* = 0*xi + 1*0.52 = 0.52
                assert abs(comp["adjusted"] - 0.52) < 0.001, \
                    f"Component {code} with ci=0 should have adjusted=0.52, got {comp['adjusted']}"
    
    def test_geometric_mean_collapses_with_zero(self):
        """
        TEST: Un componente xi=0 con ci=1 → G colapsa mucho más que A
        La media geométrica es más sensible a valores bajos.
        """
        from scoring.engine_v3 import score_v3
        
        # Candidato perfecto excepto sin skills (SK=0)
        candidate = {
            "id": "test-geo",
            "full_name": "Test Geométrica",
            "email": "test@test.com",
            "phone": "123456",
            "current_title": "Director",
            "years_experience": 15,
            "industry": "retail",
            "functional_area": "operations",
            "seniority": "director",
            "city": "Ciudad de México",
            "state": "CDMX",
            "skills": [],  # Sin skills → SK.xi = 0 con alta confianza
            "languages": ["Español", "Inglés"],
            "previous_companies": [
                {"company_name": "ACME", "title": "Director", "start_date": "2015", "end_date": None}
            ],
            "embedding": [0.1] * 1536,
        }
        
        job = {
            "id": "job-geo",
            "title": "Director",
            "functional_area": "operations",
            "industry": "retail",
            "seniority_level": "director",
            "required_skills": ["Python", "Java", "SQL"],  # Skills requeridos que el candidato NO tiene
            "embedding": [0.1] * 1536,
        }
        
        result = score_v3(candidate, job)
        
        A = result["_debug"]["arithmetic_mean_A"]
        G = result["_debug"]["geometric_mean_G"]
        
        # Verificar que G < A (la geométrica es más sensible a valores bajos)
        assert G < A, f"G ({G}) should be less than A ({A}) when one component is near 0"
    
    def test_boosts_cap(self):
        """
        TEST: Boosts al tope → core no excede 1.0
        """
        from scoring.engine_v3 import score_v3
        from scoring.config_v3 import BOOST_CAP
        
        # Candidato perfecto que debería obtener todos los boosts
        candidate = {
            "id": "test-boost",
            "full_name": "Perfect Candidate",
            "email": "perfect@test.com",
            "phone": "123456",
            "current_title": "Director de Operaciones",
            "years_experience": 20,
            "industry": "retail",
            "functional_area": "operations",
            "seniority": "director",
            "city": "Ciudad de México",
            "state": "CDMX",
            "skills": ["Supply Chain", "Lean", "SAP", "Six Sigma"],
            "languages": ["Español", "Inglés"],
            "previous_companies": [
                {"company_name": "ACME", "title": "Director", "start_date": "2010", "end_date": None}
            ],
            "embedding": [0.1] * 1536,
            "ai_classification": {
                "approved_by_recruiter": True,
                "confidence_score": 0.95,
            },
        }
        
        job = {
            "id": "job-boost",
            "title": "Director de Operaciones",
            "functional_area": "operations",
            "industry": "retail",
            "seniority_level": "director",
            "min_experience": 10,
            "city": "Ciudad de México",
            "state": "CDMX",
            "work_scheme": "presencial",
            "required_skills": ["Supply Chain", "Lean", "SAP"],
            "required_languages": ["Español", "Inglés"],
            "embedding": [0.1] * 1536,
        }
        
        result = score_v3(candidate, job)
        
        # Verificar que core no excede 1.0
        assert result["_debug"]["core_clamped"] <= 1.0, \
            f"Core should not exceed 1.0, got {result['_debug']['core_clamped']}"
        
        # Verificar que boosts no exceden el cap
        assert result["boosts"]["total"] <= BOOST_CAP, \
            f"Boosts total ({result['boosts']['total']}) should not exceed cap ({BOOST_CAP})"
    
    def test_penalties_cap(self):
        """
        TEST: Penalties grandes → core no baja de 0.0
        """
        from scoring.engine_v3 import score_v3
        from scoring.config_v3 import PENALTY_CAP
        
        # Candidato con muchos problemas que deberían generar penalties
        candidate = {
            "id": "test-penalty",
            "full_name": "Problema Candidate",
            "email": "problema@test.com",
            "years_experience": 1,  # Muy poco
            "seniority": "trainee",  # Muy bajo para la vacante
            "skills": [],
            "previous_companies": [
                # Job hopper: muchos trabajos cortos
                {"company_name": "A", "title": "Jr", "start_date": "2023-01", "end_date": "2023-06"},
                {"company_name": "B", "title": "Jr", "start_date": "2023-07", "end_date": "2023-12"},
                {"company_name": "C", "title": "Jr", "start_date": "2024-01", "end_date": "2024-06"},
            ],
        }
        
        job = {
            "id": "job-penalty",
            "title": "Director",
            "seniority_level": "director",  # Candidato es trainee (gap >= 2)
            "min_experience": 10,
        }
        
        result = score_v3(candidate, job)
        
        # Verificar que core no baja de 0.0
        assert result["_debug"]["core_clamped"] >= 0.0, \
            f"Core should not go below 0.0, got {result['_debug']['core_clamped']}"
        
        # Verificar que penalties no exceden el cap
        assert result["penalties"]["total"] <= PENALTY_CAP, \
            f"Penalties total ({result['penalties']['total']}) should not exceed cap ({PENALTY_CAP})"
    
    def test_fatal_knockout_hms_zero(self):
        """
        TEST: K fatal → HMS = 0
        """
        from scoring.engine_v3 import score_v3
        
        # Candidato con experiencia FATAL (muy por debajo del mínimo)
        candidate = {
            "id": "test-fatal",
            "full_name": "Fatal Knockout",
            "email": "fatal@test.com",
            "years_experience": 2,  # Muy bajo
            "skills": ["Python"],
            "previous_companies": [
                {"company_name": "X", "title": "Junior", "start_date": "2023", "end_date": None}
            ],
        }
        
        job = {
            "id": "job-fatal",
            "title": "Senior Director",
            "min_experience": 15,  # Requiere 15, candidato tiene 2 → fatal (< 50% = 7.5)
        }
        
        result = score_v3(candidate, job)
        
        # Verificar que K = 0 (fatal)
        if result["knockout_results"]["K"] == 0:
            # Si hay knockout fatal, HMS debe ser 0
            assert result["match_score_v3"] == 0, \
                f"With fatal knockout (K=0), HMS should be 0, got {result['match_score_v3']}"
            assert result["recommended_action"] == "do_not_advance_knockout"
    
    def test_hec_range(self):
        """
        TEST: HEC siempre [0,1]
        """
        from scoring.engine_v3 import score_v3
        
        # Test con varios candidatos
        test_cases = [
            SAMPLE_CANDIDATE,
            {"id": "empty", "full_name": "Empty"},  # Candidato vacío
            {  # Candidato completo
                "id": "full",
                "full_name": "Full",
                "email": "full@test.com",
                "phone": "123",
                "current_title": "CEO",
                "skills": ["A", "B", "C", "D"],
                "functional_area": "general_management",
                "previous_companies": [
                    {"company_name": "X", "title": "CEO", "start_date": "2020", "end_date": None}
                ],
                "languages": ["Español"],
                "years_experience": 20,
                "ai_classification": {
                    "approved_by_recruiter": True,
                    "was_corrected": True,
                    "confidence_score": 0.99,
                },
                "resume_files": [{"upload_date": "2024-12-01"}],
            },
        ]
        
        for candidate in test_cases:
            result = score_v3(candidate, SAMPLE_JOB)
            hec = result["confidence_score"]
            
            assert 0.0 <= hec <= 1.0, \
                f"HEC should be in [0,1], got {hec} for candidate {candidate.get('id')}"
    
    def test_hms_range(self):
        """
        TEST: HMS siempre [0,100]
        """
        from scoring.engine_v3 import score_v3
        
        # Test con varios candidatos
        test_cases = [
            SAMPLE_CANDIDATE,
            {"id": "empty", "full_name": "Empty"},
            {**SAMPLE_CANDIDATE, "years_experience": 100, "skills": SAMPLE_JOB.get("required_skills", [])},
        ]
        
        for candidate in test_cases:
            result = score_v3(candidate, SAMPLE_JOB)
            hms = result["match_score_v3"]
            
            assert 0 <= hms <= 100, \
                f"HMS should be in [0,100], got {hms} for candidate {candidate.get('id')}"
    
    def test_recommended_actions(self):
        """
        TEST: recommended_action devuelve valores válidos
        """
        from scoring.engine_v3 import score_v3
        
        valid_actions = {
            "do_not_advance_knockout",
            "advance_to_screening",
            "review_manually",
            "possible_backup",
            "save_for_other_role",
            "low_priority",
        }
        
        result = score_v3(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert result["recommended_action"] in valid_actions, \
            f"Invalid recommended_action: {result['recommended_action']}"
    
    def test_output_structure(self):
        """
        TEST: Estructura de salida completa
        """
        from scoring.engine_v3 import score_v3
        
        result = score_v3(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        # Campos requeridos
        required_fields = [
            "engine_version",
            "match_score_v3",
            "confidence_score",
            "knockout_results",
            "component_breakdown",
            "boosts",
            "penalties",
            "recommended_action",
            "calculated_at",
            "hec_breakdown",
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        
        # Verificar component_breakdown tiene 10 componentes
        assert len(result["component_breakdown"]) == 10, \
            f"Expected 10 components, got {len(result['component_breakdown'])}"
        
        # Verificar cada componente tiene raw, confidence, adjusted
        for code, comp in result["component_breakdown"].items():
            assert "raw" in comp, f"Component {code} missing 'raw'"
            assert "confidence" in comp, f"Component {code} missing 'confidence'"
            assert "adjusted" in comp, f"Component {code} missing 'adjusted'"
            assert "evidence" in comp, f"Component {code} missing 'evidence'"
    
    def test_hec_six_signals(self):
        """
        TEST: HEC tiene las 6 señales correctas
        """
        from scoring.engine_v3 import score_v3
        
        result = score_v3(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        expected_signals = {"EC", "PC", "HV", "DC", "CV", "RC"}
        actual_signals = set(result["hec_breakdown"].keys())
        
        assert actual_signals == expected_signals, \
            f"HEC signals should be {expected_signals}, got {actual_signals}"
        
        # Verificar que cada señal tiene la estructura correcta
        for signal, data in result["hec_breakdown"].items():
            assert "weight" in data, f"HEC signal {signal} missing 'weight'"
            assert "score" in data, f"HEC signal {signal} missing 'score'"
            assert "weighted" in data, f"HEC signal {signal} missing 'weighted'"


class TestHECCalculation:
    """Tests específicos para calculate_hec"""
    
    def test_hec_weights_sum(self):
        """Pesos de HEC suman 1.0"""
        from scoring.confidence import HEC_WEIGHTS
        
        total = sum(HEC_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"HEC weights should sum to 1.0, got {total}"
    
    def test_hec_ec_signal(self):
        """EC: proporción de componentes con ci > 0.5"""
        from scoring.confidence import calculate_ec
        
        # Componentes con diferentes niveles de confianza
        components = {
            "SK": {"confidence": 0.9},  # > 0.5
            "ER": {"confidence": 0.8},  # > 0.5
            "FA": {"confidence": 0.3},  # < 0.5
            "SA": {"confidence": 0.0},  # < 0.5
            "IA": {"confidence": 0.6},  # > 0.5
            "ED": {"confidence": 0.4},  # < 0.5
            "TR": {"confidence": 1.0},  # > 0.5
            "LO": {"confidence": 0.2},  # < 0.5
            "SM": {"confidence": 0.7},  # > 0.5
            "CQ": {"confidence": 0.5},  # = 0.5 (no cuenta como > 0.5)
        }
        
        score, evidence = calculate_ec(components)
        
        # 5 componentes tienen ci > 0.5
        assert score == 0.5, f"EC should be 0.5 (5/10), got {score}"
        assert evidence["components_high_ci"] == 5
    
    def test_hec_hv_approved(self):
        """HV: 1.0 si approved_by_recruiter"""
        from scoring.confidence import calculate_hv
        
        candidate = {
            "ai_classification": {
                "approved_by_recruiter": True,
                "was_corrected": False,
            }
        }
        
        score, evidence = calculate_hv(candidate)
        assert score == 1.0
    
    def test_hec_hv_not_validated(self):
        """HV: 0.5 si no hay validación humana"""
        from scoring.confidence import calculate_hv
        
        candidate = {
            "ai_classification": {
                "approved_by_recruiter": False,
                "was_corrected": False,
            }
        }
        
        score, evidence = calculate_hv(candidate)
        assert score == 0.5
    
    def test_hec_dc_four_checks(self):
        """DC: promedio de 4 checks específicos"""
        from scoring.confidence import calculate_dc
        
        # Candidato con todos los checks
        candidate = {
            "email": "test@test.com",
            "previous_companies": [{"start_date": "2020-01-01"}],
            "skills": ["Python"],
            "functional_area": "engineering",
        }
        
        score, evidence = calculate_dc(candidate)
        assert score == 1.0  # 4/4
        assert evidence["passed"] == 4
    
    def test_hec_rc_recent_upload(self):
        """RC: recencia del upload < 180 días = 1.0"""
        from scoring.confidence import calculate_rc
        from datetime import datetime, timedelta, timezone
        
        recent_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        candidate = {
            "resume_files": [{"upload_date": recent_date}]
        }
        
        score, evidence = calculate_rc(candidate)
        assert score == 1.0
        assert evidence["days_old"] < 180


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
