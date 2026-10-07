"""Análisis experto con Claude sobre el ranking que produce el motor de matching.

IMPORTANTE: esta capa es solo de lectura. No modifica scores, pesos ni el orden del motor:
recibe el ranking tal cual y le añade criterio humano-legible.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

from ai_model_config import ai_model_config, PROVIDER

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = """Eres Atlas, director de reclutamiento ejecutivo en México con 20 años de experiencia.

Recibes el ranking que produjo el motor de matching de la firma (scores ya calculados) y tu trabajo es
dar criterio profesional sobre cada finalista: qué tan real es el fit, qué le falta y cómo validarlo en entrevista.

REGLAS:
1. NO cambies ni cuestiones los scores numéricos: son la referencia del motor. Tu aporte es cualitativo.
2. Sé concreto y accionable: nada de frases genéricas tipo "buen perfil con experiencia relevante".
3. Si el candidato NO cumple algo crítico de la vacante, dilo sin rodeos.
4. Usa español de México, tono profesional y directo.
5. Responde SOLO con JSON válido, sin texto adicional ni bloques de código.

Formato de respuesta:
{
  "shortlist": [
    {
      "candidate_id": "id exacto recibido",
      "fit": "alto" | "medio" | "bajo",
      "verdict": "1-2 frases con la recomendación concreta",
      "strengths": ["2-4 fortalezas específicas y verificables"],
      "gaps": ["1-3 brechas reales frente a la vacante"],
      "interview_questions": ["2-3 preguntas para validar las brechas"],
      "risk_flags": ["riesgos de contratación o de proceso, vacío si no hay"]
    }
  ],
  "summary": "2-3 frases: qué tan sólida es la terna y a quién mover primero",
  "search_advice": "1-2 frases: qué ajustar en la búsqueda si la terna es débil"
}
"""


def _extract_json(text: str) -> Dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class AIMatchReviewService:
    def __init__(self, db, matching_service, api_key: str):
        self.db = db
        self.matching_service = matching_service
        self.api_key = api_key

    @staticmethod
    def _candidate_brief(result: Dict, rank: int, candidate: Optional[Dict]) -> Dict:
        breakdown = result.get("breakdown") or {}
        scores = {
            key: value.get("score")
            for key, value in breakdown.items()
            if isinstance(value, dict) and "score" in value
        }
        return {
            "rank": rank,
            "candidate_id": result.get("candidate_id"),
            "name": result.get("candidate_name"),
            "current_title": result.get("current_title"),
            "current_company": result.get("current_company"),
            "seniority": result.get("seniority"),
            "area": (candidate or {}).get("presentation_area"),
            "subarea": (candidate or {}).get("presentation_subarea"),
            "industry": result.get("industry"),
            "years_experience": result.get("years_experience"),
            "match_score": result.get("match_percentage"),
            "score_breakdown": scores,
            "boosts": breakdown.get("boost_reasons"),
            "penalties": breakdown.get("penalty_reasons"),
            "skills_missing": (result.get("missing_skills") or [])[:8],
            "engine_strengths": (result.get("strengths") or [])[:5],
            "engine_risks": [
                r.get("message") if isinstance(r, dict) else r
                for r in (result.get("risks") or [])[:5]
            ],
            "profile_summary": ((candidate or {}).get("ai_summary") or "")[:700],
        }

    async def _ask_claude(self, job: Dict, briefs: List[Dict], model: str) -> Dict:
        payload = {
            "vacante": {
                "titulo": job.get("title"),
                "empresa": job.get("company"),
                "industria": job.get("industry"),
                "area": job.get("presentation_area") or job.get("functional_area"),
                "subarea": job.get("presentation_subarea"),
                "seniority": job.get("presentation_seniority") or job.get("seniority"),
                "experiencia_minima": job.get("min_experience") or job.get("min_years_experience"),
                "objetivo_del_puesto": (job.get("job_objective") or "")[:1500],
                "contexto_del_rol": (job.get("role_context") or "")[:1500],
                "responsabilidades": (job.get("responsibilities") or job.get("responsibilities_old") or "")[:2000],
                "experiencia_requerida": (job.get("required_experience") or job.get("requirements") or "")[:1500],
                "no_negociables": (job.get("non_negotiables") or "")[:1200],
                "skills_requeridos": job.get("required_skills"),
                "skills_deseables": job.get("preferred_skills") or job.get("nice_to_have"),
                "scorecard": job.get("job_scorecard"),
                "ubicacion": " / ".join(filter(None, [job.get("location_city"), job.get("location_state"),
                                                     job.get("location_country"), job.get("location")])),
                "modalidad": job.get("work_scheme") or job.get("work_mode"),
                "descripcion": (job.get("description") or "")[:2000],
            },
            "finalistas_del_motor": briefs,
        }
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"match-review-{job.get('id')}-{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM_MESSAGE,
        ).with_model(PROVIDER, model)
        message = UserMessage(text=json.dumps(payload, ensure_ascii=False))
        response = await asyncio.to_thread(lambda: asyncio.run(chat.send_message(message)))
        return _extract_json(response)

    async def review(self, job: Dict, top_n: int = 5, threshold: int = 60,
                     actor: Optional[str] = None) -> Dict:
        matching = await self.matching_service.match_candidates(job=job, threshold=threshold, limit=top_n)
        results = (matching.get("results") or [])[:top_n]
        if not results:
            return {
                "job_id": job.get("id"),
                "total_reviewed": 0,
                "shortlist": [],
                "summary": "El motor no devolvió candidatos por encima del umbral; no hay terna que analizar.",
                "search_advice": "Baja el umbral o amplía área/seniority de la búsqueda.",
                "model": None,
            }

        ids = [r.get("candidate_id") for r in results if r.get("candidate_id")]
        docs = await self.db.candidates.find(
            {"id": {"$in": ids}}, {"_id": 0, "embedding": 0}
        ).to_list(len(ids))
        by_id = {d["id"]: d for d in docs}
        briefs = [self._candidate_brief(r, i + 1, by_id.get(r.get("candidate_id")))
                  for i, r in enumerate(results)]

        model = await ai_model_config.get_model("match_review")
        analysis = await self._ask_claude(job, briefs, model)

        by_candidate = {item.get("candidate_id"): item for item in (analysis.get("shortlist") or [])}
        shortlist = []
        for brief in briefs:
            item = by_candidate.get(brief["candidate_id"], {})
            cand = by_id.get(brief["candidate_id"]) or {}
            shortlist.append({
                "candidate_id": brief["candidate_id"],
                "name": brief["name"],
                "current_title": brief["current_title"],
                "current_company": brief["current_company"],
                "email": cand.get("email"),
                "phone": cand.get("phone"),
                "linkedin_url": cand.get("linkedin_url"),
                "has_cv": bool(cand.get("resume_files")),
                "rank": brief["rank"],
                "match_score": brief["match_score"],
                "fit": item.get("fit"),
                "verdict": item.get("verdict"),
                "strengths": item.get("strengths") or [],
                "gaps": item.get("gaps") or [],
                "interview_questions": item.get("interview_questions") or [],
                "risk_flags": item.get("risk_flags") or [],
            })

        review = {
            "id": str(uuid.uuid4()),
            "job_id": job.get("id"),
            "job_title": job.get("title"),
            "model": model,
            "threshold": threshold,
            "total_reviewed": len(shortlist),
            "shortlist": shortlist,
            "summary": analysis.get("summary"),
            "search_advice": analysis.get("search_advice"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": actor,
        }
        await self.db.ai_match_reviews.update_one(
            {"job_id": job.get("id")}, {"$set": review}, upsert=True
        )
        return review

    async def get_cached(self, job_id: str) -> Optional[Dict]:
        return await self.db.ai_match_reviews.find_one({"job_id": job_id}, {"_id": 0})
