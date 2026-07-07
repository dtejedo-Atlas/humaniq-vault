import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Servicio de generación de embeddings para búsqueda semántica.
    
    Usa la API de OpenAI para generar embeddings. 
    Requiere una key de OpenAI válida (OPENAI_API_KEY).
    
    NOTA: La EMERGENT_LLM_KEY funciona para chat pero NO para embeddings directos.
    Para embeddings, se necesita una OPENAI_API_KEY separada.
    Si no hay key configurada, los embeddings se desactivan silenciosamente.
    """
    
    def __init__(self):
        # Intentar usar OPENAI_API_KEY primero, luego EMERGENT_LLM_KEY
        self.api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('EMERGENT_LLM_KEY')
        self.client = None
        self.model = "text-embedding-3-small"
        self.dimensions = 1536
        self.enabled = False
        
        # Solo inicializar si hay una key que NO sea emergent (ya que no funciona para embeddings)
        openai_key = os.environ.get('OPENAI_API_KEY')
        if openai_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=openai_key)
                self.enabled = True
                logger.info("Embedding service initialized with OpenAI API key")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {str(e)}")
        else:
            logger.info(
                "Embedding service disabled - no OPENAI_API_KEY configured. "
                "Candidates will be saved but semantic search will not work. "
                "To enable, add OPENAI_API_KEY to backend/.env"
            )
    
    def _build_searchable_text(self, candidate: dict) -> str:
        """
        Build rich searchable text from candidate data for embedding
        """
        parts = []
        
        # Basic info
        if name := candidate.get('full_name'):
            parts.append(f"Nombre: {name}")
        
        if title := candidate.get('current_title'):
            parts.append(f"Título: {title}")
        
        if company := candidate.get('current_company'):
            parts.append(f"Empresa: {company}")
        
        # Professional classification
        if industry := candidate.get('industry'):
            parts.append(f"Industria: {industry}")
        
        if area := candidate.get('functional_area'):
            parts.append(f"Área funcional: {area}")
        
        if exp := candidate.get('years_experience'):
            parts.append(f"Experiencia: {exp} años")
        
        if seniority := candidate.get('seniority'):
            parts.append(f"Nivel: {seniority}")
        
        # Skills and languages
        if skills := candidate.get('skills'):
            parts.append(f"Habilidades: {', '.join(skills)}")
        
        if languages := candidate.get('languages'):
            parts.append(f"Idiomas: {', '.join(languages)}")
        
        # AI summary
        if summary := candidate.get('ai_summary'):
            parts.append(f"Resumen: {summary}")
        
        # Work history
        if companies := candidate.get('previous_companies'):
            for company in companies[:3]:  # Top 3 previous companies
                if company_name := company.get('company_name'):
                    company_title = company.get('title', '')
                    parts.append(f"Experiencia previa: {company_title} en {company_name}")
        
        return " | ".join(filter(None, parts))
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        Returns None if embeddings are disabled or on error.
        """
        if not self.enabled or not self.client:
            logger.debug("Embeddings disabled - skipping generation")
            return None
        
        if not text or not text.strip():
            return None
        
        try:
            # Clean text
            cleaned_text = text.replace("\n", " ").strip()
            
            # Generate embedding (cliente síncrono → thread aparte para no bloquear el event loop)
            response = await asyncio.to_thread(
                self.client.embeddings.create,
                model=self.model,
                input=cleaned_text
            )
            
            return response.data[0].embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            # Don't return zeros - return None to indicate failure
            return None
    
    async def generate_candidate_embedding(self, candidate: dict) -> Optional[List[float]]:
        """
        Generate embedding for a candidate profile.
        Returns None if disabled or on error.
        """
        if not self.enabled:
            return None
        searchable_text = self._build_searchable_text(candidate)
        return await self.generate_embedding(searchable_text)
    
    async def generate_batch_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batch (more efficient).
        Returns list of embeddings or None for each text.
        """
        if not self.enabled or not self.client:
            return [None] * len(texts)
        
        if not texts:
            return []
        
        try:
            # Clean texts
            cleaned_texts = [t.replace("\n", " ").strip() for t in texts if t and t.strip()]
            
            if not cleaned_texts:
                return [None] * len(texts)
            
            # Generate embeddings in batch (cliente síncrono → thread aparte)
            response = await asyncio.to_thread(
                self.client.embeddings.create,
                model=self.model,
                input=cleaned_texts
            )
            
            # Sort by index to preserve order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            return [None] * len(texts)
    
    @staticmethod
    def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        Returns: float between 0.0 and 1.0
        """
        if not embedding1 or not embedding2:
            return 0.0
        
        try:
            # Convert to numpy arrays
            vec1 = np.array([embedding1])
            vec2 = np.array([embedding2])
            
            # Calculate cosine similarity
            similarity = cosine_similarity(vec1, vec2)[0][0]
            
            # Convert to 0-1 range (cosine is -1 to 1)
            return float((similarity + 1) / 2)
        
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    @staticmethod
    def find_top_similar(query_embedding: List[float], candidate_embeddings: List[tuple], top_k: int = 50) -> List[dict]:
        """
        Find top K most similar candidates
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of (candidate_id, embedding) tuples
            top_k: Number of top results to return
        
        Returns:
            List of {candidate_id, similarity_score} dicts
        """
        if not query_embedding or not candidate_embeddings:
            return []
        
        try:
            query_vec = np.array([query_embedding])
            
            results = []
            for candidate_id, embedding in candidate_embeddings:
                if not embedding:
                    continue
                
                candidate_vec = np.array([embedding])
                similarity = cosine_similarity(query_vec, candidate_vec)[0][0]
                
                # Convert to 0-1 range
                score = float((similarity + 1) / 2)
                
                results.append({
                    "candidate_id": candidate_id,
                    "similarity_score": score
                })
            
            # Sort by similarity and return top K
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"Error finding similar candidates: {str(e)}")
            return []

embedding_service = EmbeddingService()
