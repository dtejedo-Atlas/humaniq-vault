"""
Job Matching Service
====================
Motor de matching de candidatos contra vacantes.
Usa el modelo de scoring v2.1 adaptado para evaluación estructurada.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging

from scoring_config import (
    WEIGHTS,
    BOOSTS,
    PENALTIES,
    SENIORITY_DISTANCE_SCORES,
    MULTIPLICADORES_EXPERIENCIA,
)
from affinity_matrices import (
    get_functional_affinity,
    get_industry_transferability,
    are_adjacent_functions,
)
from trajectory_analyzer import (
    calculate_experience_level,
    calculate_trajectory_score,
    calculate_stability_score,
    get_seniority_index,
    calculate_gm_evidence,
)
from query_parser import infer_seniority_from_title

logger = logging.getLogger(__name__)

# Pesos específicos para Job Matching (ajustados vs búsqueda libre)
JOB_MATCH_WEIGHTS = {
    "funcional": 0.35,      # Área funcional
    "seniority": 0.20,      # Nivel jerárquico
    "industria": 0.15,      # Industria
    "skills": 0.12,         # Skills match (más importante en matching)
    "experiencia": 0.08,    # Años de experiencia
    "semantico": 0.05,      # Similitud semántica
    "trayectoria": 0.05,    # Consistencia de carrera
}

# Threshold mínimo para incluir en resultados de matching
JOB_MATCH_THRESHOLD = 60

# Mapeo de seniority texto a índice
SENIORITY_TO_INDEX = {
    "intern": 1, "entry": 1,
    "junior": 3,
    "mid": 4,
    "senior": 6,
    "lead": 6,
    "manager": 7,
    "senior_manager": 8,
    "director": 9,
    "vp": 10,
    "c_level": 11,
    "ceo": 12,
}


class JobMatchingService:
    """Servicio de matching candidato-vacante"""
    
    def __init__(self, db, embedding_service):
        self.db = db
        self.embedding_service = embedding_service
    
    # ========== GENERACIÓN DE EMBEDDING PARA VACANTE ==========
    
    def _build_job_searchable_text(self, job: dict) -> str:
        """Construye texto searchable de la vacante para embedding"""
        parts = []
        
        if title := job.get("title"):
            parts.append(f"Puesto: {title}")
        
        if area := job.get("functional_area"):
            parts.append(f"Área: {area}")
        
        if industry := job.get("industry"):
            parts.append(f"Industria: {industry}")
        
        if seniority := job.get("seniority"):
            parts.append(f"Nivel: {seniority}")
        
        if responsibilities := job.get("responsibilities"):
            parts.append(f"Responsabilidades: {responsibilities}")
        
        if requirements := job.get("requirements"):
            parts.append(f"Requisitos: {requirements}")
        
        if skills := job.get("required_skills"):
            parts.append(f"Skills requeridos: {', '.join(skills)}")
        
        if preferred := job.get("preferred_skills"):
            parts.append(f"Skills deseables: {', '.join(preferred)}")
        
        if description := job.get("description"):
            parts.append(f"Descripción: {description}")
        
        if context := job.get("role_context"):
            parts.append(f"Contexto: {context}")
        
        return " | ".join(filter(None, parts))
    
    async def generate_job_embedding(self, job: dict) -> Optional[List[float]]:
        """Genera embedding para una vacante"""
        if not self.embedding_service or not self.embedding_service.enabled:
            return None
        
        searchable_text = self._build_job_searchable_text(job)
        return await self.embedding_service.generate_embedding(searchable_text)
    
    # ========== CÁLCULO DE COMPONENTES DE SCORE ==========
    
    def _calculate_functional_score(self, candidate: dict, job: dict) -> Tuple[float, str]:
        """Calcula score de área funcional"""
        job_area = job.get("functional_area", "")
        candidate_area = candidate.get("functional_area", "")
        
        if not job_area:
            return (70, "principal")
        
        # Si área actual coincide exactamente
        if candidate_area and candidate_area.lower() == job_area.lower():
            return (100, "principal")
        
        # Score base de matriz de afinidad
        base_score = get_functional_affinity(candidate_area, job_area)
        
        # Determinar nivel de experiencia en el área
        exp_level = calculate_experience_level(candidate, job_area)
        
        # Aplicar multiplicador
        multiplier = MULTIPLICADORES_EXPERIENCIA.get(exp_level, 1.0)
        final_score = base_score * multiplier
        
        return (final_score, exp_level)
    
    def _calculate_seniority_score(self, candidate: dict, job: dict) -> Tuple[float, int, str]:
        """
        Calcula score de seniority.
        Retorna (score, distance, detail)
        """
        job_seniority = job.get("seniority", "")
        job_index = SENIORITY_TO_INDEX.get(job_seniority.lower(), 7)
        
        candidate_index = get_seniority_index(candidate)
        
        distance = abs(candidate_index - job_index)
        score = SENIORITY_DISTANCE_SCORES.get(distance, 0)
        if distance > 5:
            score = 0
        
        # Generar detalle
        if distance == 0:
            detail = "Nivel exacto"
        elif candidate_index > job_index:
            detail = f"Candidato {distance} nivel(es) arriba"
        else:
            detail = f"Candidato {distance} nivel(es) abajo"
        
        return (score, distance, detail)
    
    def _calculate_industry_score(self, candidate: dict, job: dict) -> Tuple[float, str]:
        """Calcula score de industria"""
        job_industry = job.get("industry", "")
        candidate_industry = candidate.get("industry", "")
        
        if not job_industry:
            return (70, "Sin industria específica")
        
        if candidate_industry and candidate_industry.lower() == job_industry.lower():
            return (100, "Industria exacta")
        
        score = get_industry_transferability(candidate_industry, job_industry)
        
        if score >= 70:
            detail = "Industria transferible"
        elif score >= 50:
            detail = "Industria parcialmente transferible"
        else:
            detail = "Cambio de industria significativo"
        
        return (score, detail)
    
    def _calculate_skills_score(self, candidate: dict, job: dict) -> Tuple[float, List[str], List[str]]:
        """
        Calcula score de skills.
        Retorna (score, matched_skills, missing_skills)
        """
        required_skills = [s.lower() for s in job.get("required_skills", [])]
        preferred_skills = [s.lower() for s in job.get("preferred_skills", [])]
        candidate_skills = [s.lower() for s in candidate.get("skills", [])]
        
        if not required_skills and not preferred_skills:
            return (80, [], [])  # Sin requisitos de skills
        
        # Calcular matches
        matched_required = []
        missing_required = []
        matched_preferred = []
        
        for skill in required_skills:
            found = False
            for cand_skill in candidate_skills:
                if skill in cand_skill or cand_skill in skill:
                    matched_required.append(skill)
                    found = True
                    break
            if not found:
                missing_required.append(skill)
        
        for skill in preferred_skills:
            for cand_skill in candidate_skills:
                if skill in cand_skill or cand_skill in skill:
                    matched_preferred.append(skill)
                    break
        
        # Calcular score
        # Required skills tienen peso 70%, preferred 30%
        if required_skills:
            required_ratio = len(matched_required) / len(required_skills)
        else:
            required_ratio = 1.0
        
        if preferred_skills:
            preferred_ratio = len(matched_preferred) / len(preferred_skills)
        else:
            preferred_ratio = 1.0
        
        score = (required_ratio * 0.7 + preferred_ratio * 0.3) * 100
        
        all_matched = matched_required + matched_preferred
        
        return (score, all_matched, missing_required)
    
    def _calculate_experience_score(self, candidate: dict, job: dict) -> Tuple[float, str]:
        """Calcula score de años de experiencia"""
        candidate_exp = candidate.get("years_experience") or 0
        min_exp = job.get("min_experience") or 0
        max_exp = job.get("max_experience")
        
        if min_exp == 0 and max_exp is None:
            return (80, "Sin requisito de experiencia")
        
        # Dentro del rango
        if candidate_exp >= min_exp:
            if max_exp is None or candidate_exp <= max_exp:
                return (100, f"{candidate_exp} años (dentro del rango)")
        
        # Por debajo del mínimo
        if candidate_exp < min_exp:
            gap = min_exp - candidate_exp
            if gap <= 2:
                score = 70
                detail = f"{candidate_exp} años ({gap} menos del mínimo)"
            elif gap <= 5:
                score = 40
                detail = f"{candidate_exp} años ({gap} menos del mínimo)"
            else:
                score = 20
                detail = f"{candidate_exp} años (muy por debajo del mínimo)"
            return (score, detail)
        
        # Por encima del máximo
        if max_exp and candidate_exp > max_exp:
            gap = candidate_exp - max_exp
            if gap <= 3:
                return (85, f"{candidate_exp} años (ligeramente sobre el máximo)")
            elif gap <= 7:
                return (70, f"{candidate_exp} años (sobre el máximo)")
            else:
                return (50, f"{candidate_exp} años (muy sobre el máximo - posible overqualified)")
        
        return (80, f"{candidate_exp} años")
    
    def _calculate_semantic_score(
        self, 
        candidate_embedding: Optional[List[float]], 
        job_embedding: Optional[List[float]]
    ) -> float:
        """Calcula similitud semántica entre candidato y vacante"""
        if not candidate_embedding or not job_embedding:
            return 0
        
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            cand_vec = np.array([candidate_embedding])
            job_vec = np.array([job_embedding])
            
            raw_similarity = cosine_similarity(cand_vec, job_vec)[0][0]
            
            # Normalizar
            if raw_similarity < 0.2:
                return 0
            
            normalized = (raw_similarity - 0.2) / 0.7
            return max(0, min(100, normalized * 100))
            
        except Exception as e:
            logger.error(f"Error calculating semantic similarity: {str(e)}")
            return 0
    
    # ========== DETECCIÓN DE RIESGOS ==========
    
    def _detect_risks(
        self, 
        candidate: dict, 
        job: dict, 
        scores: dict
    ) -> List[Dict[str, Any]]:
        """Detecta riesgos potenciales del candidato"""
        risks = []
        
        # Riesgo de estabilidad
        stability_warning = scores.get("stability_warning", "none")
        if stability_warning == "high":
            risks.append({
                "type": "stability",
                "severity": "high",
                "detail": "Alta rotación laboral detectada"
            })
        elif stability_warning == "moderate":
            risks.append({
                "type": "stability",
                "severity": "moderate",
                "detail": "Rotación laboral moderada"
            })
        
        # Riesgo de cambio de industria
        industry_score = scores.get("industria_score", 100)
        if industry_score < 50:
            risks.append({
                "type": "industry_change",
                "severity": "moderate",
                "detail": f"Cambio de industria significativo ({scores.get('industria_detail', '')})"
            })
        
        # Riesgo de overqualified
        seniority_distance = scores.get("seniority_distance", 0)
        candidate_index = get_seniority_index(candidate)
        job_index = SENIORITY_TO_INDEX.get(job.get("seniority", "").lower(), 7)
        
        if candidate_index > job_index + 2:
            risks.append({
                "type": "overqualified",
                "severity": "moderate" if seniority_distance <= 3 else "high",
                "detail": f"Candidato {seniority_distance} niveles por encima del puesto"
            })
        
        # Riesgo de underqualified
        if candidate_index < job_index - 2:
            risks.append({
                "type": "underqualified",
                "severity": "high" if seniority_distance >= 3 else "moderate",
                "detail": f"Candidato {seniority_distance} niveles por debajo del puesto"
            })
        
        # Riesgo de gap de experiencia
        exp_score = scores.get("experiencia_score", 100)
        if exp_score < 50:
            risks.append({
                "type": "experience_gap",
                "severity": "moderate",
                "detail": scores.get("experiencia_detail", "Gap de experiencia")
            })
        
        # Riesgo de skills faltantes
        missing_skills = scores.get("missing_skills", [])
        if len(missing_skills) >= 3:
            risks.append({
                "type": "skill_gap",
                "severity": "high" if len(missing_skills) >= 5 else "moderate",
                "detail": f"Faltan {len(missing_skills)} skills requeridos"
            })
        
        return risks
    
    # ========== DETECCIÓN DE FORTALEZAS ==========
    
    def _detect_strengths(self, candidate: dict, job: dict, scores: dict) -> List[str]:
        """Detecta fortalezas principales del candidato"""
        strengths = []
        
        # Fortaleza funcional
        if scores.get("funcional_score", 0) >= 90:
            strengths.append("Experiencia directa en el área funcional requerida")
        elif scores.get("exp_level") == "principal":
            strengths.append("Carrera construida en el área funcional")
        
        # Fortaleza de seniority
        if scores.get("seniority_score", 0) >= 90:
            strengths.append("Nivel de seniority adecuado para el puesto")
        
        # Fortaleza de industria
        if scores.get("industria_score", 0) >= 90:
            strengths.append("Experiencia en la industria objetivo")
        elif scores.get("industria_score", 0) >= 70:
            strengths.append("Industria transferible")
        
        # Fortaleza de skills
        skills_score = scores.get("skills_score", 0)
        matched_skills = scores.get("matched_skills", [])
        if skills_score >= 80 and matched_skills:
            strengths.append(f"Cumple {len(matched_skills)} skills clave")
        
        # Fortaleza de experiencia
        if scores.get("experiencia_score", 0) >= 90:
            strengths.append("Años de experiencia dentro del rango solicitado")
        
        # Fortaleza de trayectoria
        if scores.get("trayectoria_score", 0) >= 80:
            strengths.append("Trayectoria profesional consistente")
        
        # Estabilidad
        if scores.get("stability_warning") == "none":
            strengths.append("Buena estabilidad laboral")
        
        return strengths[:5]  # Máximo 5 fortalezas
    
    # ========== CÁLCULO DE MATCH TOTAL ==========
    
    def _calculate_match(
        self, 
        candidate: dict, 
        job: dict, 
        job_embedding: Optional[List[float]]
    ) -> Dict[str, Any]:
        """Calcula el match completo de un candidato contra una vacante"""
        
        # 1. Calcular cada componente
        func_score, exp_level = self._calculate_functional_score(candidate, job)
        seniority_score, seniority_distance, seniority_detail = self._calculate_seniority_score(candidate, job)
        industry_score, industry_detail = self._calculate_industry_score(candidate, job)
        skills_score, matched_skills, missing_skills = self._calculate_skills_score(candidate, job)
        exp_score, exp_detail = self._calculate_experience_score(candidate, job)
        
        candidate_embedding = candidate.get("embedding")
        semantic_score = self._calculate_semantic_score(candidate_embedding, job_embedding)
        
        trajectory_score = calculate_trajectory_score(candidate)
        stability_score, stability_warning, stability_detail = calculate_stability_score(candidate)
        
        # 2. Almacenar scores para análisis
        scores = {
            "funcional_score": func_score,
            "exp_level": exp_level,
            "seniority_score": seniority_score,
            "seniority_distance": seniority_distance,
            "seniority_detail": seniority_detail,
            "industria_score": industry_score,
            "industria_detail": industry_detail,
            "skills_score": skills_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "experiencia_score": exp_score,
            "experiencia_detail": exp_detail,
            "semantico_score": semantic_score,
            "trayectoria_score": trajectory_score,
            "estabilidad_score": stability_score,
            "stability_warning": stability_warning,
            "stability_detail": stability_detail,
        }
        
        # 3. Calcular score ponderado
        weighted_score = (
            func_score * JOB_MATCH_WEIGHTS["funcional"] +
            seniority_score * JOB_MATCH_WEIGHTS["seniority"] +
            industry_score * JOB_MATCH_WEIGHTS["industria"] +
            skills_score * JOB_MATCH_WEIGHTS["skills"] +
            exp_score * JOB_MATCH_WEIGHTS["experiencia"] +
            semantic_score * JOB_MATCH_WEIGHTS["semantico"] +
            trajectory_score * JOB_MATCH_WEIGHTS["trayectoria"]
        )
        
        # 4. Calcular boosts
        boosts = 0
        boost_reasons = []
        
        if func_score >= 100 and exp_level == "principal":
            boosts += 10
            boost_reasons.append("match_exacto_funcion")
        
        if industry_score >= 100:
            boosts += 5
            boost_reasons.append("match_exacto_industria")
        
        if seniority_distance == 0:
            boosts += 5
            boost_reasons.append("match_exacto_seniority")
        
        if skills_score >= 90:
            boosts += 5
            boost_reasons.append("skills_completos")
        
        # 5. Calcular penalties
        penalties = 0
        penalty_reasons = []
        
        # Penalty por GM sin evidencia
        candidate_area = candidate.get("functional_area", "")
        if candidate_area and candidate_area.lower() == "general_management":
            gm_evidence = calculate_gm_evidence(candidate, job.get("functional_area"))
            if gm_evidence == "ninguna":
                penalties += 20
                penalty_reasons.append("gm_sin_evidencia")
            elif gm_evidence == "débil":
                penalties += 15
                penalty_reasons.append("gm_evidencia_debil")
            elif gm_evidence == "moderada":
                penalties += 8
                penalty_reasons.append("gm_evidencia_moderada")
        
        # Penalty por seniority muy diferente
        if seniority_distance >= 4:
            penalties += 10
            penalty_reasons.append("seniority_muy_diferente")
        
        # 6. Score final
        final_score = weighted_score + boosts - penalties
        final_score = max(0, min(100, round(final_score)))
        
        # 7. Detectar fortalezas y riesgos
        strengths = self._detect_strengths(candidate, job, scores)
        risks = self._detect_risks(candidate, job, scores)
        
        # 8. Construir breakdown
        breakdown = {
            "funcional": {
                "score": round(func_score),
                "weight": f"{JOB_MATCH_WEIGHTS['funcional']*100:.0f}%",
                "exp_level": exp_level,
                "detail": f"Área: {candidate_area or 'N/A'} → {job.get('functional_area', 'N/A')}"
            },
            "seniority": {
                "score": round(seniority_score),
                "weight": f"{JOB_MATCH_WEIGHTS['seniority']*100:.0f}%",
                "distance": seniority_distance,
                "detail": seniority_detail
            },
            "industria": {
                "score": round(industry_score),
                "weight": f"{JOB_MATCH_WEIGHTS['industria']*100:.0f}%",
                "detail": industry_detail
            },
            "skills": {
                "score": round(skills_score),
                "weight": f"{JOB_MATCH_WEIGHTS['skills']*100:.0f}%",
                "matched": len(matched_skills),
                "total_required": len(job.get("required_skills", [])),
                "detail": f"{len(matched_skills)}/{len(job.get('required_skills', []))} skills requeridos"
            },
            "experiencia": {
                "score": round(exp_score),
                "weight": f"{JOB_MATCH_WEIGHTS['experiencia']*100:.0f}%",
                "detail": exp_detail
            },
            "semantico": {
                "score": round(semantic_score),
                "weight": f"{JOB_MATCH_WEIGHTS['semantico']*100:.0f}%",
                "detail": "Similitud de perfil" if semantic_score > 0 else "Sin embedding"
            },
            "trayectoria": {
                "score": round(trajectory_score),
                "weight": f"{JOB_MATCH_WEIGHTS['trayectoria']*100:.0f}%",
                "detail": "Consistencia de carrera"
            },
            "estabilidad": {
                "score": round(stability_score),
                "warning": stability_warning,
                "detail": stability_detail
            },
            "boosts": boosts,
            "boost_reasons": boost_reasons,
            "penalties": penalties,
            "penalty_reasons": penalty_reasons,
            "weighted_base": round(weighted_score),
        }
        
        return {
            "match_percentage": final_score,
            "breakdown": breakdown,
            "strengths": strengths,
            "risks": risks,
            "missing_skills": missing_skills,
        }
    
    # ========== MÉTODO PRINCIPAL DE MATCHING ==========
    
    async def match_candidates(
        self, 
        job: dict, 
        threshold: int = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Ejecuta matching de todos los candidatos contra una vacante.
        
        Args:
            job: Diccionario con datos de la vacante
            threshold: Score mínimo para incluir (default: JOB_MATCH_THRESHOLD)
            limit: Máximo de resultados
        
        Returns:
            Dict con resultados de matching
        """
        effective_threshold = threshold if threshold is not None else JOB_MATCH_THRESHOLD
        
        # 1. Obtener embedding de la vacante
        job_embedding = job.get("embedding")
        if not job_embedding and self.embedding_service and self.embedding_service.enabled:
            job_embedding = await self.generate_job_embedding(job)
        
        # 2. Obtener todos los candidatos
        candidates = await self.db.candidates.find(
            {},
            {"_id": 0}
        ).to_list(500)
        
        logger.info(f"Matching {len(candidates)} candidates against job '{job.get('title')}'")
        
        # 3. Calcular match para cada candidato
        results = []
        
        for candidate in candidates:
            match_data = self._calculate_match(candidate, job, job_embedding)
            
            if match_data["match_percentage"] >= effective_threshold:
                results.append({
                    "candidate_id": candidate.get("id"),
                    "candidate_name": candidate.get("full_name", ""),
                    "current_title": candidate.get("current_title"),
                    "current_company": candidate.get("current_company"),
                    "match_percentage": match_data["match_percentage"],
                    "breakdown": match_data["breakdown"],
                    "strengths": match_data["strengths"],
                    "risks": match_data["risks"],
                    "missing_skills": match_data["missing_skills"],
                    "years_experience": candidate.get("years_experience"),
                    "industry": candidate.get("industry"),
                    "functional_area": candidate.get("functional_area"),
                    "seniority": candidate.get("seniority"),
                })
        
        # 4. Ordenar por match_percentage
        results.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        logger.info(f"Found {len(results)} candidates above threshold {effective_threshold}")
        
        return {
            "job_id": job.get("id"),
            "job_title": job.get("title"),
            "total_candidates": len(candidates),
            "matched_candidates": len(results),
            "threshold_used": effective_threshold,
            "results": results[:limit]
        }


# Factory function
def create_job_matching_service(db, embedding_service):
    """Crea instancia del servicio de matching"""
    return JobMatchingService(db, embedding_service)
