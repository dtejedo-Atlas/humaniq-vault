from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class HybridSearchService:
    def __init__(self, db, embedding_service):
        self.db = db
        self.embedding_service = embedding_service
    
    def _build_mongo_query(self, filters: dict) -> dict:
        """Build MongoDB query from filters"""
        query = {}
        
        if status := filters.get('status'):
            query['status'] = status
        
        if industry := filters.get('industry'):
            query['industry'] = industry
        
        if functional_area := filters.get('functional_area'):
            query['functional_area'] = functional_area
        
        if seniority := filters.get('seniority'):
            query['seniority'] = seniority
        
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
        
        # Languages
        if languages := filters.get('languages'):
            if isinstance(languages, list):
                query['languages'] = {'$in': languages}
            else:
                query['languages'] = languages
        
        return query
    
    async def _keyword_search(self, query: str, filters: dict, limit: int = 100) -> List[dict]:
        """Keyword-based search using regex"""
        mongo_query = self._build_mongo_query(filters)
        
        # Add text search conditions
        if query:
            mongo_query['$or'] = [
                {'full_name': {'$regex': query, '$options': 'i'}},
                {'email': {'$regex': query, '$options': 'i'}},
                {'current_company': {'$regex': query, '$options': 'i'}},
                {'current_title': {'$regex': query, '$options': 'i'}},
                {'skills': {'$regex': query, '$options': 'i'}},
                {'ai_summary': {'$regex': query, '$options': 'i'}}
            ]
        
        results = await self.db.candidates.find(
            mongo_query,
            {"_id": 0}
        ).limit(limit).to_list(limit)
        
        return results
    
    async def _vector_search(self, query_embedding: List[float], filters: dict, limit: int = 50) -> List[dict]:
        """
        Vector similarity search
        Note: This is manual cosine similarity. For production with large datasets,
        consider MongoDB Atlas Vector Search or external vector DB.
        """
        # Get base filtered candidates
        mongo_query = self._build_mongo_query(filters)
        mongo_query['embedding'] = {'$exists': True, '$ne': None}
        
        candidates = await self.db.candidates.find(
            mongo_query,
            {"_id": 0, "id": 1, "embedding": 1, "full_name": 1, "current_title": 1}
        ).to_list(1000)  # Limit to 1000 for performance
        
        if not candidates:
            return []
        
        # Calculate similarities
        candidate_embeddings = [
            (c['id'], c.get('embedding', []))
            for c in candidates
            if c.get('embedding')
        ]
        
        similar_results = self.embedding_service.find_top_similar(
            query_embedding,
            candidate_embeddings,
            top_k=limit
        )
        
        # Fetch full candidate data for top results
        candidate_ids = [r['candidate_id'] for r in similar_results]
        
        full_candidates = await self.db.candidates.find(
            {"id": {"$in": candidate_ids}},
            {"_id": 0}
        ).to_list(limit)
        
        # Add similarity scores
        id_to_score = {r['candidate_id']: r['similarity_score'] for r in similar_results}
        for candidate in full_candidates:
            candidate['vector_score'] = id_to_score.get(candidate['id'], 0.0)
        
        # Sort by score
        full_candidates.sort(key=lambda x: x.get('vector_score', 0.0), reverse=True)
        
        return full_candidates
    
    def _merge_and_rank(
        self,
        structured_results: List[dict],
        keyword_results: List[dict],
        semantic_results: List[dict],
        weights: Dict[str, float]
    ) -> List[dict]:
        """
        Merge and rank results from different search methods
        """
        # Create a map of candidate_id -> combined data
        candidate_map = {}
        
        # Add structured results (highest weight)
        for candidate in structured_results:
            candidate_id = candidate['id']
            candidate_map[candidate_id] = {
                'candidate': candidate,
                'scores': {
                    'structured': 1.0,
                    'keyword': 0.0,
                    'semantic': 0.0
                }
            }
        
        # Add keyword results
        for candidate in keyword_results:
            candidate_id = candidate['id']
            if candidate_id not in candidate_map:
                candidate_map[candidate_id] = {
                    'candidate': candidate,
                    'scores': {
                        'structured': 0.0,
                        'keyword': 1.0,
                        'semantic': 0.0
                    }
                }
            else:
                candidate_map[candidate_id]['scores']['keyword'] = 1.0
        
        # Add semantic results
        for candidate in semantic_results:
            candidate_id = candidate['id']
            semantic_score = candidate.get('vector_score', 0.0)
            
            if candidate_id not in candidate_map:
                candidate_map[candidate_id] = {
                    'candidate': candidate,
                    'scores': {
                        'structured': 0.0,
                        'keyword': 0.0,
                        'semantic': semantic_score
                    }
                }
            else:
                candidate_map[candidate_id]['scores']['semantic'] = semantic_score
        
        # Calculate weighted scores
        ranked_results = []
        for candidate_id, data in candidate_map.items():
            scores = data['scores']
            
            # Weighted sum
            total_score = (
                scores['structured'] * weights.get('structured', 1.0) +
                scores['keyword'] * weights.get('keyword', 0.7) +
                scores['semantic'] * weights.get('semantic', 0.9)
            )
            
            candidate = data['candidate'].copy()
            candidate['match_score'] = round(total_score * 100)  # Convert to 0-100
            candidate['match_breakdown'] = {
                'structured': bool(scores['structured']),
                'keyword': bool(scores['keyword']),
                'semantic': round(scores['semantic'] * 100)
            }
            
            ranked_results.append(candidate)
        
        # Sort by total score
        ranked_results.sort(key=lambda x: x['match_score'], reverse=True)
        
        return ranked_results
    
    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[dict] = None,
        use_semantic: bool = True,
        limit: int = 50
    ) -> List[dict]:
        """
        Hybrid search: combines structured filters, keyword search, and semantic search
        """
        if filters is None:
            filters = {}
        
        # A) STRUCTURED SEARCH (exact filters)
        structured_results = []
        if filters:
            mongo_query = self._build_mongo_query(filters)
            if not query:  # If no query, return filtered results
                structured_results = await self.db.candidates.find(
                    mongo_query,
                    {"_id": 0}
                ).limit(limit).to_list(limit)
        
        # B) KEYWORD SEARCH
        keyword_results = []
        if query:
            keyword_results = await self._keyword_search(query, filters, limit=100)
        
        # C) SEMANTIC SEARCH
        semantic_results = []
        if use_semantic and query:
            try:
                query_embedding = await self.embedding_service.generate_embedding(query)
                semantic_results = await self._vector_search(query_embedding, filters, limit=50)
            except Exception as e:
                logger.error(f"Semantic search failed: {str(e)}")
        
        # If only filters (no query), return structured results
        if not query:
            return structured_results[:limit]
        
        # D) MERGE AND RANK
        combined_results = self._merge_and_rank(
            structured_results,
            keyword_results,
            semantic_results,
            weights={
                'structured': 1.0,
                'keyword': 0.7,
                'semantic': 0.9
            }
        )
        
        return combined_results[:limit]
