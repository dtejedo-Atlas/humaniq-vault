"""
Hybrid Search Service - Versión Calibrada
==========================================

Combina búsqueda estructurada, por keywords y semántica con:
- Threshold de relevancia configurable
- Scores normalizados correctamente (0-100%)
- Filtrado inteligente de resultados poco relevantes
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ============= CONFIGURACIÓN DE BÚSQUEDA =============

# Threshold mínimo de similitud semántica (0.0 - 1.0)
# Solo candidatos con score >= este valor se consideran relevantes
SEMANTIC_THRESHOLD = 0.30  # ~30% de similitud mínima

# Threshold mínimo de score final para incluir en resultados
MIN_MATCH_SCORE = 35  # Score mínimo de 35/100

# Pesos para combinar los diferentes tipos de búsqueda
SEARCH_WEIGHTS = {
    'structured': 1.0,   # Filtros exactos (máxima prioridad)
    'keyword': 0.9,      # Match por keywords (aumentado)
    'semantic': 0.7      # Similitud semántica
}

# Boost por match de keyword (cuando hay coincidencia textual + semántica)
KEYWORD_BOOST = 20  # Aumentado para priorizar keyword matches


class HybridSearchService:
    def __init__(self, db, embedding_service):
        self.db = db
        self.embedding_service = embedding_service
    
    def _build_mongo_query(self, filters: dict) -> dict:
        """Build MongoDB query from filters"""
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
        
        # Years of experience range
        if min_exp := filters.get('min_experience'):
            query.setdefault('years_experience', {})['$gte'] = min_exp
        
        if max_exp := filters.get('max_experience'):
            query.setdefault('years_experience', {})['$lte'] = max_exp
        
        # Location
        if city := filters.get('city'):
            query['city'] = {'$regex': city, '$options': 'i'}
        
        if state := filters.get('state'):
            query['state'] = {'$regex': state, '$options': 'i'}
        
        # Skills (array contains)
        if skills := filters.get('skills'):
            if isinstance(skills, list):
                query['skills'] = {'$in': skills}
            else:
                query['skills'] = skills
        
        return query
    
    async def _keyword_search(self, query: str, filters: dict, limit: int = 100) -> List[dict]:
        """Keyword-based search using regex with accent normalization"""
        from text_utils import normalize_for_search
        
        mongo_query = self._build_mongo_query(filters)
        
        if query:
            query_normalized = normalize_for_search(query)
            query_words = query_normalized.split()
            
            # Crear condiciones OR para cada palabra del query
            or_conditions = []
            for word in query_words:
                if len(word) >= 3:  # Ignorar palabras muy cortas
                    or_conditions.extend([
                        {'full_name_normalized': {'$regex': word, '$options': 'i'}},
                        {'company_normalized': {'$regex': word, '$options': 'i'}},
                        {'title_normalized': {'$regex': word, '$options': 'i'}},
                        {'full_name': {'$regex': word, '$options': 'i'}},
                        {'current_company': {'$regex': word, '$options': 'i'}},
                        {'current_title': {'$regex': word, '$options': 'i'}},
                        {'skills': {'$regex': word, '$options': 'i'}},
                        {'ai_summary': {'$regex': word, '$options': 'i'}}
                    ])
            
            if or_conditions:
                mongo_query['$or'] = or_conditions
        
        results = await self.db.candidates.find(
            mongo_query,
            {"_id": 0}
        ).limit(limit).to_list(limit)
        
        # Calcular score de keyword basado en cuántas palabras coinciden
        if query:
            query_words_set = set(query.lower().split())
            for candidate in results:
                keyword_matches = 0
                searchable_text = ' '.join([
                    str(candidate.get('full_name', '')),
                    str(candidate.get('current_title', '')),
                    str(candidate.get('current_company', '')),
                    str(candidate.get('ai_summary', '')),
                    ' '.join(candidate.get('skills', []))
                ]).lower()
                
                for word in query_words_set:
                    if len(word) >= 3 and word in searchable_text:
                        keyword_matches += 1
                
                # Score de keyword: proporción de palabras encontradas
                candidate['keyword_score'] = keyword_matches / max(len(query_words_set), 1)
        
        return results
    
    def _calculate_semantic_similarity(self, query_embedding: List[float], candidate_embedding: List[float]) -> float:
        """
        Calcula similitud coseno normalizada
        """
        if not query_embedding or not candidate_embedding:
            return 0.0
        
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            query_vec = np.array([query_embedding])
            candidate_vec = np.array([candidate_embedding])
            
            # Cosine similarity devuelve -1 a 1
            raw_similarity = cosine_similarity(query_vec, candidate_vec)[0][0]
            
            # Para embeddings de texto profesional, los valores típicos son 0.3-0.8
            # Normalizamos de [0.2, 0.9] a [0.0, 1.0] para mejor discriminación
            if raw_similarity < 0.2:
                return 0.0
            
            normalized = (raw_similarity - 0.2) / 0.7
            return max(0.0, min(1.0, normalized))
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    async def _semantic_search(self, query_embedding: List[float], filters: dict, limit: int = 50) -> List[dict]:
        """
        Búsqueda semántica con threshold de relevancia
        """
        mongo_query = self._build_mongo_query(filters)
        mongo_query['embedding'] = {'$exists': True, '$ne': None}
        
        candidates = await self.db.candidates.find(
            mongo_query,
            {"_id": 0}
        ).to_list(1000)
        
        if not candidates:
            return []
        
        results_with_scores = []
        
        for candidate in candidates:
            embedding = candidate.get('embedding')
            if not embedding or len(embedding) < 100:
                continue
            
            # Calcular similitud semántica real
            similarity = self._calculate_semantic_similarity(query_embedding, embedding)
            
            # APLICAR THRESHOLD: Solo incluir si supera el mínimo
            if similarity >= SEMANTIC_THRESHOLD:
                candidate['semantic_score'] = similarity
                results_with_scores.append(candidate)
        
        # Ordenar por score semántico descendente
        results_with_scores.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)
        
        return results_with_scores[:limit]
    
    def _merge_and_rank(
        self,
        keyword_results: List[dict],
        semantic_results: List[dict],
        query: str
    ) -> List[dict]:
        """
        Merge y ranking inteligente con threshold de relevancia
        """
        candidate_map = {}
        
        # Procesar resultados de keyword
        for candidate in keyword_results:
            candidate_id = candidate['id']
            candidate_map[candidate_id] = {
                'candidate': candidate,
                'keyword_score': candidate.get('keyword_score', 0.5),  # Default si no se calculó
                'semantic_score': 0.0,
                'has_keyword': True,
                'has_semantic': False
            }
        
        # Procesar resultados semánticos
        for candidate in semantic_results:
            candidate_id = candidate['id']
            semantic_score = candidate.get('semantic_score', 0.0)
            
            if candidate_id in candidate_map:
                # Existe en keyword también - boost!
                candidate_map[candidate_id]['semantic_score'] = semantic_score
                candidate_map[candidate_id]['has_semantic'] = True
            else:
                # Solo en semántica
                candidate_map[candidate_id] = {
                    'candidate': candidate,
                    'keyword_score': 0.0,
                    'semantic_score': semantic_score,
                    'has_keyword': False,
                    'has_semantic': True
                }
        
        # Calcular score final para cada candidato
        ranked_results = []
        
        for candidate_id, data in candidate_map.items():
            keyword_score = data['keyword_score']
            semantic_score = data['semantic_score']
            has_keyword = data['has_keyword']
            has_semantic = data['has_semantic']
            
            # Score base: combinación ponderada
            base_score = (
                keyword_score * SEARCH_WEIGHTS['keyword'] +
                semantic_score * SEARCH_WEIGHTS['semantic']
            )
            
            # Normalizar a 0-100
            max_possible = SEARCH_WEIGHTS['keyword'] + SEARCH_WEIGHTS['semantic']
            match_score = (base_score / max_possible) * 100
            
            # BOOST: Si tiene tanto keyword como semántica, es muy relevante
            if has_keyword and has_semantic:
                match_score += KEYWORD_BOOST
            
            # Aplicar threshold de score mínimo
            if match_score < MIN_MATCH_SCORE and not has_keyword:
                # Si no tiene keyword match y score bajo, excluir
                continue
            
            # Limitar a 100 máximo
            match_score = min(100, round(match_score))
            
            candidate = data['candidate'].copy()
            candidate['match_score'] = match_score
            candidate['match_breakdown'] = {
                'keyword': has_keyword,
                'keyword_score': round(keyword_score * 100),
                'semantic': round(semantic_score * 100),
                'boosted': has_keyword and has_semantic
            }
            
            ranked_results.append(candidate)
        
        # Ordenar por score final
        ranked_results.sort(key=lambda x: x['match_score'], reverse=True)
        
        return ranked_results
    
    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[dict] = None,
        use_semantic: bool = True,
        limit: int = 50,
        min_score: int = None  # Override del threshold
    ) -> List[dict]:
        """
        Búsqueda híbrida calibrada
        
        Args:
            query: Texto de búsqueda
            filters: Filtros estructurados (industria, área, etc.)
            use_semantic: Si usar búsqueda semántica
            limit: Máximo de resultados
            min_score: Score mínimo para incluir (override de MIN_MATCH_SCORE)
        
        Returns:
            Lista de candidatos ordenados por relevancia, filtrados por threshold
        """
        if filters is None:
            filters = {}
        
        # Limpiar filtros vacíos
        filters = {k: v for k, v in filters.items() if v and str(v).strip()}
        
        effective_min_score = min_score if min_score is not None else MIN_MATCH_SCORE
        
        # A) SOLO FILTROS (sin query de texto)
        if not query:
            mongo_query = self._build_mongo_query(filters)
            results = await self.db.candidates.find(
                mongo_query,
                {"_id": 0}
            ).limit(limit).to_list(limit)
            
            # Sin query, todos tienen match perfecto por filtros
            for r in results:
                r['match_score'] = 100
                r['match_breakdown'] = {'structured': True, 'keyword': False, 'semantic': 0}
            
            return results
        
        # B) KEYWORD SEARCH
        keyword_results = await self._keyword_search(query, filters, limit=100)
        logger.info(f"Keyword search found {len(keyword_results)} candidates")
        
        # C) SEMANTIC SEARCH
        semantic_results = []
        if use_semantic and self.embedding_service.enabled:
            try:
                query_embedding = await self.embedding_service.generate_embedding(query)
                if query_embedding:
                    semantic_results = await self._semantic_search(query_embedding, filters, limit=50)
                    logger.info(f"Semantic search found {len(semantic_results)} candidates above threshold")
            except Exception as e:
                logger.error(f"Semantic search failed: {str(e)}")
        
        # D) MERGE Y RANKING
        combined_results = self._merge_and_rank(
            keyword_results,
            semantic_results,
            query
        )
        
        # E) APLICAR THRESHOLD FINAL
        filtered_results = [
            r for r in combined_results 
            if r['match_score'] >= effective_min_score
        ]
        
        logger.info(f"After threshold ({effective_min_score}): {len(filtered_results)} candidates")
        
        return filtered_results[:limit]


# Función factory para crear instancia
def create_hybrid_search_service(db, embedding_service):
    return HybridSearchService(db, embedding_service)
