"""
Hybrid Search Service v2.1 - Scoring Multi-dimensional
=======================================================

Sistema de búsqueda híbrida con scoring explicable basado en:
- Área funcional principal (40%)
- Seniority/nivel jerárquico (20%)
- Industria (15%)
- Similitud semántica (13%)
- Trayectoria profesional (5%)
- Keywords textuales (5%)
- Estabilidad laboral (2%)
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging
import numpy as np

from scoring_config import (
    WEIGHTS,
    MIN_MATCH_SCORE,
    SEMANTIC_THRESHOLD,
    MAX_RESULTS,
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
from query_parser import (
    parse_query,
    extract_keywords,
    infer_seniority_from_title,
)
from trajectory_analyzer import (
    calculate_experience_level,
    calculate_trajectory_score,
    calculate_stability_score,
    calculate_stability_penalty,
    get_seniority_index,
    calculate_gm_evidence,
)

logger = logging.getLogger(__name__)


class HybridSearchService:
    """Servicio de búsqueda híbrida con scoring v2.1"""
    
    def __init__(self, db, embedding_service):
        self.db = db
        self.embedding_service = embedding_service
    
    # ========== CONSTRUCCIÓN DE QUERY MONGODB ==========
    
    def _build_mongo_query(self, filters: dict) -> dict:
        """Construye query MongoDB desde filtros estructurados"""
        query = {}
        
        if status := filters.get('status'):
            if status.strip():
                query['status'] = status.strip()
        
        if industry := filters.get('industry'):
            if industry.strip():
                query['industry'] = industry.strip()
        
        if functional_area := filters.get('functional_area'):
            if functional_area.strip():
                query['functional_area'] = functional_area.strip()
        
        if seniority := filters.get('seniority'):
            if seniority.strip():
                query['seniority'] = seniority.strip()
        
        if min_exp := filters.get('min_experience'):
            query.setdefault('years_experience', {})['$gte'] = min_exp
        
        if max_exp := filters.get('max_experience'):
            query.setdefault('years_experience', {})['$lte'] = max_exp
        
        if city := filters.get('city'):
            query['city'] = {'$regex': city, '$options': 'i'}
        
        if state := filters.get('state'):
            query['state'] = {'$regex': state, '$options': 'i'}
        
        if skills := filters.get('skills'):
            if isinstance(skills, list):
                query['skills'] = {'$in': skills}
            else:
                query['skills'] = skills
        
        return query
    
    # ========== BÚSQUEDAS BASE ==========
    
    async def _get_all_candidates(self, filters: dict, limit: int = 200) -> List[dict]:
        """Obtiene candidatos que cumplen con los filtros base"""
        mongo_query = self._build_mongo_query(filters)
        
        results = await self.db.candidates.find(
            mongo_query,
            {"_id": 0}
        ).limit(limit).to_list(limit)
        
        return results
    
    def _calculate_semantic_similarity(
        self, 
        query_embedding: List[float], 
        candidate_embedding: List[float]
    ) -> float:
        """Calcula similitud coseno normalizada (0.0 - 1.0)"""
        if not query_embedding or not candidate_embedding:
            return 0.0
        
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            query_vec = np.array([query_embedding])
            candidate_vec = np.array([candidate_embedding])
            
            raw_similarity = cosine_similarity(query_vec, candidate_vec)[0][0]
            
            # Normalizar de [0.2, 0.9] a [0.0, 1.0]
            if raw_similarity < 0.2:
                return 0.0
            
            normalized = (raw_similarity - 0.2) / 0.7
            return max(0.0, min(1.0, normalized))
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    # ========== CÁLCULO DE COMPONENTES DE SCORE ==========
    
    def _calculate_functional_score(
        self, 
        candidate: dict, 
        query_parsed: dict
    ) -> Tuple[float, str]:
        """
        Calcula score de área funcional (0-100).
        Retorna (score, experience_level).
        """
        query_area = query_parsed.get("area_funcional")
        candidate_area = candidate.get("functional_area", "")
        
        if not query_area:
            # Sin área específica en query, score neutral
            return (70, "principal")
        
        # Score base de matriz de afinidad
        base_score = get_functional_affinity(candidate_area, query_area)
        
        # Determinar nivel de experiencia en el área
        exp_level = calculate_experience_level(candidate, query_area)
        
        # Aplicar multiplicador según nivel de experiencia
        multiplier = MULTIPLICADORES_EXPERIENCIA.get(exp_level, 1.0)
        final_score = base_score * multiplier
        
        return (final_score, exp_level)
    
    def _calculate_seniority_score(
        self, 
        candidate: dict, 
        query_parsed: dict
    ) -> Tuple[float, int]:
        """
        Calcula score de seniority (0-100).
        Retorna (score, distance).
        """
        query_seniority = query_parsed.get("seniority_index")
        candidate_seniority = get_seniority_index(candidate)
        
        if not query_seniority:
            # Sin seniority específico en query, score alto
            return (80, 0)
        
        distance = abs(candidate_seniority - query_seniority)
        
        # Score basado en distancia
        score = SENIORITY_DISTANCE_SCORES.get(distance, 0)
        if distance > 5:
            score = 0
        
        return (score, distance)
    
    def _calculate_industry_score(
        self, 
        candidate: dict, 
        query_parsed: dict
    ) -> float:
        """Calcula score de industria (0-100)"""
        query_industry = query_parsed.get("industria")
        candidate_industry = candidate.get("industry", "")
        
        if not query_industry:
            # Sin industria específica, score neutral
            return 70
        
        return get_industry_transferability(candidate_industry, query_industry)
    
    def _calculate_semantic_score(
        self, 
        candidate: dict, 
        query_embedding: Optional[List[float]]
    ) -> float:
        """Calcula score semántico (0-100)"""
        if not query_embedding:
            return 0
        
        candidate_embedding = candidate.get("embedding")
        if not candidate_embedding or len(candidate_embedding) < 100:
            return 0
        
        similarity = self._calculate_semantic_similarity(query_embedding, candidate_embedding)
        
        # Aplicar threshold
        if similarity < SEMANTIC_THRESHOLD:
            return 0
        
        # Convertir a score 0-100
        return similarity * 100
    
    def _calculate_keyword_score(
        self, 
        candidate: dict, 
        query_parsed: dict
    ) -> Tuple[float, bool]:
        """
        Calcula score de keywords (0-100).
        Retorna (score, keyword_in_title).
        """
        keywords = query_parsed.get("keywords", [])
        raw_query = query_parsed.get("raw_query", "").lower()
        
        if not keywords:
            return (0, False)
        
        # Campos a buscar con pesos
        current_title = str(candidate.get("current_title", "")).lower()
        current_company = str(candidate.get("current_company", "")).lower()
        ai_summary = str(candidate.get("ai_summary", "")).lower()
        skills = " ".join(candidate.get("skills", [])).lower()
        
        # Contar matches
        matches = 0
        title_match = False
        
        for keyword in keywords:
            if len(keyword) < 3:
                continue
            
            # Título tiene peso triple
            if keyword in current_title:
                matches += 3
                title_match = True
            # Otros campos peso 1
            if keyword in current_company:
                matches += 1
            if keyword in ai_summary:
                matches += 1
            if keyword in skills:
                matches += 2
        
        # Calcular score basado en proporción
        max_possible = len(keywords) * 7  # 3+1+1+2 por keyword
        if max_possible == 0:
            return (0, False)
        
        score = (matches / max_possible) * 100
        
        # Verificar si query aparece en título
        keyword_in_title = raw_query in current_title or title_match
        
        return (min(100, score), keyword_in_title)
    
    # ========== CÁLCULO DE BOOSTS Y PENALTIES ==========
    
    def _calculate_boosts(
        self,
        candidate: dict,
        query_parsed: dict,
        scores: dict
    ) -> Tuple[int, List[str]]:
        """
        Calcula boosts positivos.
        Retorna (total_boost, lista_de_razones).
        """
        total = 0
        reasons = []
        
        query_area = query_parsed.get("area_funcional")
        candidate_area = candidate.get("functional_area", "")
        
        # Match exacto de función
        if query_area and candidate_area and candidate_area.lower() == query_area.lower():
            if scores.get("exp_level") == "principal":
                total += BOOSTS["match_exacto_funcion"]
                reasons.append("match_exacto_funcion")
        
        # Match exacto de industria
        query_industry = query_parsed.get("industria")
        candidate_industry = candidate.get("industry", "")
        if query_industry and candidate_industry and candidate_industry.lower() == query_industry.lower():
            total += BOOSTS["match_exacto_industria"]
            reasons.append("match_exacto_industria")
        
        # Match exacto de seniority
        if scores.get("seniority_distance", 99) <= 1:
            total += BOOSTS["match_exacto_seniority"]
            reasons.append("match_exacto_seniority")
        
        # Keyword en título
        if scores.get("keyword_in_title"):
            total += BOOSTS["keyword_en_titulo"]
            reasons.append("keyword_en_titulo")
        
        # Trayectoria consistente
        if scores.get("trayectoria", 0) >= 80:
            total += BOOSTS["trayectoria_consistente"]
            reasons.append("trayectoria_consistente")
        
        # Skills match alto
        skills_matched = self._count_skill_matches(candidate, query_parsed)
        if skills_matched >= 4:
            total += BOOSTS["skills_match_alto"]
            reasons.append("skills_match_alto")
        
        return (total, reasons)
    
    def _calculate_penalties(
        self,
        candidate: dict,
        query_parsed: dict,
        scores: dict
    ) -> Tuple[int, List[str]]:
        """
        Calcula penalties negativos.
        Retorna (total_penalty, lista_de_razones).
        """
        total = 0
        reasons = []
        
        candidate_area = candidate.get("functional_area", "")
        query_area = query_parsed.get("area_funcional")
        
        # Penalty por GM en búsqueda funcional
        if candidate_area and candidate_area.lower() == "general_management" and query_area:
            evidence = calculate_gm_evidence(candidate, query_area)
            
            if evidence == "ninguna":
                total += PENALTIES["gm_sin_evidencia"]
                reasons.append("gm_sin_evidencia")
            elif evidence == "débil":
                total += PENALTIES["gm_evidencia_debil"]
                reasons.append("gm_evidencia_debil")
            elif evidence == "moderada":
                total += PENALTIES["gm_evidencia_moderada"]
                reasons.append("gm_evidencia_moderada")
            # "fuerte" → sin penalty
        
        # Penalty por distancia de seniority
        seniority_distance = scores.get("seniority_distance", 0)
        if seniority_distance >= 5:
            total += PENALTIES["seniority_5_niveles"]
            reasons.append("seniority_5_niveles")
        elif seniority_distance == 4:
            total += PENALTIES["seniority_4_niveles"]
            reasons.append("seniority_4_niveles")
        elif seniority_distance == 3:
            total += PENALTIES["seniority_3_niveles"]
            reasons.append("seniority_3_niveles")
        
        # Penalty por función adyacente
        if candidate_area and query_area and are_adjacent_functions(candidate_area, query_area):
            total += PENALTIES["funcion_adyacente"]
            reasons.append("funcion_adyacente")
        
        # Penalty por industria no transferible
        if scores.get("industria", 100) < 30:
            total += PENALTIES["industria_no_transferible"]
            reasons.append("industria_no_transferible")
        
        # Penalty por estabilidad
        stability_warning = scores.get("stability_warning", "none")
        stability_penalty = calculate_stability_penalty(stability_warning)
        if stability_penalty > 0:
            total += stability_penalty
            reasons.append(f"estabilidad_{stability_warning}")
        
        return (total, reasons)
    
    def _count_skill_matches(self, candidate: dict, query_parsed: dict) -> int:
        """Cuenta cuántos skills del candidato coinciden con la query"""
        keywords = query_parsed.get("keywords", [])
        skills = candidate.get("skills", [])
        
        if not keywords or not skills:
            return 0
        
        skills_lower = [s.lower() for s in skills]
        matches = 0
        
        for keyword in keywords:
            for skill in skills_lower:
                if keyword in skill:
                    matches += 1
                    break
        
        return matches
    
    # ========== SCORING PRINCIPAL ==========
    
    def _calculate_final_score(
        self,
        candidate: dict,
        query_parsed: dict,
        query_embedding: Optional[List[float]]
    ) -> dict:
        """
        Calcula el score final multi-dimensional para un candidato.
        
        Returns:
            Dict con match_score y match_breakdown detallado
        """
        # 1. Calcular cada componente
        func_score, exp_level = self._calculate_functional_score(candidate, query_parsed)
        seniority_score, seniority_distance = self._calculate_seniority_score(candidate, query_parsed)
        industry_score = self._calculate_industry_score(candidate, query_parsed)
        semantic_score = self._calculate_semantic_score(candidate, query_embedding)
        keyword_score, keyword_in_title = self._calculate_keyword_score(candidate, query_parsed)
        trajectory_score = calculate_trajectory_score(candidate)
        stability_score, stability_warning, stability_detail = calculate_stability_score(candidate)
        
        # 2. Almacenar scores para boosts/penalties
        scores = {
            "funcional": func_score,
            "exp_level": exp_level,
            "seniority": seniority_score,
            "seniority_distance": seniority_distance,
            "industria": industry_score,
            "semantico": semantic_score,
            "keywords": keyword_score,
            "keyword_in_title": keyword_in_title,
            "trayectoria": trajectory_score,
            "estabilidad": stability_score,
            "stability_warning": stability_warning,
        }
        
        # 3. Calcular score ponderado
        weighted_score = (
            func_score * WEIGHTS["funcional"] +
            seniority_score * WEIGHTS["seniority"] +
            industry_score * WEIGHTS["industria"] +
            semantic_score * WEIGHTS["semantico"] +
            keyword_score * WEIGHTS["keywords"] +
            trajectory_score * WEIGHTS["trayectoria"] +
            stability_score * WEIGHTS["estabilidad"]
        )
        
        # 4. Calcular boosts y penalties
        boosts, boost_reasons = self._calculate_boosts(candidate, query_parsed, scores)
        penalties, penalty_reasons = self._calculate_penalties(candidate, query_parsed, scores)
        
        # 5. Score final
        final_score = weighted_score + boosts - penalties
        final_score = max(0, min(100, round(final_score)))
        
        # 6. Construir breakdown detallado
        breakdown = {
            "funcional": round(func_score),
            "exp_level": exp_level,
            "seniority": round(seniority_score),
            "seniority_distance": seniority_distance,
            "industria": round(industry_score),
            "semantico": round(semantic_score),
            "keywords": round(keyword_score),
            "keyword_in_title": keyword_in_title,
            "trayectoria": round(trajectory_score),
            "estabilidad": {
                "score": round(stability_score),
                "warning": stability_warning,
                "detalle": stability_detail
            },
            "boosts": boosts,
            "boost_reasons": boost_reasons,
            "penalties": penalties,
            "penalty_reasons": penalty_reasons,
            "weighted_base": round(weighted_score),
        }
        
        return {
            "match_score": final_score,
            "match_breakdown": breakdown
        }
    
    # ========== MÉTODO PRINCIPAL DE BÚSQUEDA ==========
    
    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[dict] = None,
        use_semantic: bool = True,
        limit: int = None,
        min_score: int = None
    ) -> List[dict]:
        """
        Búsqueda híbrida con scoring v2.1.
        
        Args:
            query: Texto de búsqueda
            filters: Filtros estructurados (industria, área, etc.)
            use_semantic: Si usar búsqueda semántica
            limit: Máximo de resultados
            min_score: Score mínimo para incluir (override)
        
        Returns:
            Lista de candidatos ordenados por relevancia
        """
        if filters is None:
            filters = {}
        
        # Limpiar filtros vacíos
        filters = {k: v for k, v in filters.items() if v and str(v).strip()}
        
        effective_limit = limit if limit else MAX_RESULTS
        effective_min_score = min_score if min_score is not None else MIN_MATCH_SCORE
        
        # A) SOLO FILTROS (sin query de texto)
        if not query:
            results = await self._get_all_candidates(filters, effective_limit)
            
            # Sin query, todos tienen match perfecto por filtros
            for r in results:
                r['match_score'] = 100
                r['match_breakdown'] = {
                    'structured_only': True,
                    'message': 'Filtrado por criterios estructurados'
                }
            
            return results
        
        # B) PARSEAR QUERY
        query_parsed = parse_query(query)
        logger.info(f"Query parsed: area={query_parsed.get('area_funcional')}, "
                   f"seniority={query_parsed.get('seniority_index')}, "
                   f"industria={query_parsed.get('industria')}")
        
        # C) OBTENER EMBEDDING SI CORRESPONDE
        query_embedding = None
        if use_semantic and self.embedding_service and self.embedding_service.enabled:
            try:
                query_embedding = await self.embedding_service.generate_embedding(query)
            except Exception as e:
                logger.error(f"Error getting query embedding: {str(e)}")
        
        # D) OBTENER CANDIDATOS BASE
        # Primero buscar con filtros, luego sin filtros si hay pocos resultados
        candidates = await self._get_all_candidates(filters, 200)
        
        if len(candidates) < 10 and filters:
            # Ampliar búsqueda sin filtros restrictivos
            candidates_extra = await self._get_all_candidates({}, 200)
            # Agregar solo los que no están ya
            existing_ids = {c['id'] for c in candidates}
            for c in candidates_extra:
                if c['id'] not in existing_ids:
                    candidates.append(c)
        
        logger.info(f"Total candidates to score: {len(candidates)}")
        
        # E) CALCULAR SCORE PARA CADA CANDIDATO
        scored_results = []
        
        for candidate in candidates:
            score_data = self._calculate_final_score(
                candidate, 
                query_parsed, 
                query_embedding
            )
            
            # Aplicar threshold
            if score_data['match_score'] >= effective_min_score:
                candidate_result = candidate.copy()
                candidate_result['match_score'] = score_data['match_score']
                candidate_result['match_breakdown'] = score_data['match_breakdown']
                scored_results.append(candidate_result)
        
        # F) ORDENAR Y LIMITAR
        scored_results.sort(key=lambda x: x['match_score'], reverse=True)
        
        logger.info(f"Results after threshold ({effective_min_score}): {len(scored_results)}")
        
        return scored_results[:effective_limit]


# Factory function
def create_hybrid_search_service(db, embedding_service):
    """Crea instancia del servicio de búsqueda híbrida"""
    return HybridSearchService(db, embedding_service)
