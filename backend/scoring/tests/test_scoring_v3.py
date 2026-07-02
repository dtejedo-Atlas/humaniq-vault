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
        assert result["value"] == 1.0
    
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


class TestLocationKnockout:
    """Tests para evaluate_location_knockout"""
    
    def test_location_remote(self):
        """Knockout: trabajo remoto"""
        job = {**SAMPLE_JOB, "work_scheme": "remoto"}
        
        result = evaluate_location_knockout(SAMPLE_CANDIDATE, job)
        
        assert result["status"] == "cumple"
        assert result["value"] == 1.0
    
    def test_location_match(self):
        """Knockout: ubicación coincide"""
        result = evaluate_location_knockout(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert result["status"] == "cumple"


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


class TestSalaryKnockout:
    """Tests para evaluate_salary_knockout"""
    
    def test_salary_always_insufficient_evidence(self):
        """Knockout: salary siempre devuelve evidencia_insuficiente"""
        result = evaluate_salary_knockout(SAMPLE_CANDIDATE, SAMPLE_JOB)
        
        assert result["status"] == "evidencia_insuficiente"
        assert result["value"] == 0.85
        assert "no está poblado" in result["note"]


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
