"""Afinar con IA: criterios en lenguaje natural verificados contra el texto completo del CV.

- Capa 2 sobre el ranking v3 (snapshot). Caché por (candidato, criterio, versión de CV).
- Nunca infiere: sin evidencia textual → "no_cumple" (sin evidencia).
- Persistencia por vacante en `job_ai_refinements`; evaluaciones en `ai_criteria_evaluations`.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

from ai_model_config import ai_model_config, estimate_cost_usd
from cv_fulltext_service import get_cv_text, average_cv_chars
from industry_trajectory import coverage_by_industry, job_target_industries

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"
MAX_PARALLEL = 5
MAX_CV_CHARS = 24000
STATUS_SCORE = {"cumple": 1.0, "parcial": 0.5, "no_cumple": 0.0}

SYSTEM_MESSAGE = """Eres un verificador de evidencia para reclutamiento ejecutivo. Recibes el TEXTO COMPLETO de un CV y UN criterio.
Debes decidir si el CV demuestra el criterio, usando ÚNICAMENTE lo que está escrito.

Reglas estrictas:
- "cumple": el CV lo demuestra explícitamente. "parcial": hay evidencia relacionada pero incompleta o indirecta.
  "no_cumple": no hay evidencia en el texto.
- PROHIBIDO inferir, suponer o completar con conocimiento externo (ej. no asumas que una empresa es de telecom si el CV no lo dice;
  sí puedes reconocer nombres de empresas inequívocos como Telcel, AT&T, Movistar como evidencia de la industria).
- La cita (quote) debe ser TEXTUAL del CV (máximo 240 caracteres), sin paráfrasis. Si no hay evidencia, quote = null.
- Indica empresa y periodo (tal como aparecen en el CV) donde está la evidencia; null si no aplica.
Responde SOLO JSON: {"status":"cumple|parcial|no_cumple","quote":string|null,"company":string|null,"period":string|null,"reason":string(<=200)}"""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _extract_json(text: str) -> Dict:
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Respuesta sin JSON")
    return json.loads(text[start:end + 1])


class AIRefineService:
    def __init__(self, db, api_key: str):
        self.db = db
        self.api_key = api_key

    # ------------------------------------------------------------------ evaluación
    async def _ask(self, model: str, criterion: str, cv_text: str, candidate: Dict) -> Dict:
        payload = {
            "criterio": criterion,
            "candidato": {"nombre": candidate.get("full_name"), "puesto_actual": candidate.get("current_title"),
                          "empresa_actual": candidate.get("current_company")},
            "cv_texto": cv_text[:MAX_CV_CHARS],
        }
        chat = LlmChat(api_key=self.api_key, session_id=f"refine-{uuid.uuid4().hex[:10]}",
                       system_message=SYSTEM_MESSAGE).with_model(PROVIDER, model)
        text = json.dumps(payload, ensure_ascii=False)
        response = await chat.send_message(UserMessage(text=text))
        data = _extract_json(response)
        status = data.get("status") if data.get("status") in STATUS_SCORE else "no_cumple"
        quote = data.get("quote") or None
        if status != "no_cumple" and not quote:
            status = "no_cumple"  # sin cita textual no hay evidencia válida
        in_tokens, out_tokens = len(text) // 4 + 400, 120
        return {"status": status, "quote": quote, "company": data.get("company"), "period": data.get("period"),
                "reason": (data.get("reason") or "")[:300], "no_evidence": status == "no_cumple" and not quote,
                "model": model, "input_tokens": in_tokens, "output_tokens": out_tokens,
                "cost_usd": estimate_cost_usd(model, in_tokens, out_tokens)}

    async def evaluate_one(self, model: str, criterion: str, candidate: Dict, sem: asyncio.Semaphore) -> Dict:
        key = _norm(criterion)
        cv = await get_cv_text(self.db, candidate)
        cached = await self.db.ai_criteria_evaluations.find_one(
            {"candidate_id": candidate["id"], "criterion_key": key, "cv_key": cv["cv_key"]}, {"_id": 0})
        if cached:
            return {**cached, "from_cache": True, "cost_usd": 0.0}
        if not cv["text"]:
            result = {"status": "no_cumple", "quote": None, "company": None, "period": None, "no_evidence": True,
                      "reason": "Sin texto de CV disponible", "model": None, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        else:
            async with sem:
                try:
                    result = await self._ask(model, criterion, cv["text"], candidate)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Afinar IA falló para %s: %s", candidate.get("id"), e)
                    return {"candidate_id": candidate["id"], "status": "error", "quote": None, "company": None, "period": None,
                            "reason": str(e)[:200], "no_evidence": True, "cost_usd": 0.0, "from_cache": False}
        doc = {**result, "candidate_id": candidate["id"], "criterion_key": key, "criterion": criterion, "cv_key": cv["cv_key"],
               "evaluated_at": datetime.now(timezone.utc).isoformat()}
        await self.db.ai_criteria_evaluations.update_one(
            {"candidate_id": candidate["id"], "criterion_key": key, "cv_key": cv["cv_key"]}, {"$set": doc}, upsert=True)
        return {**doc, "from_cache": False}

    async def evaluate(self, job: Dict, criterion: str, candidate_ids: List[str], scope: str, actor: Optional[str],
                       on_done=None) -> Dict:
        """Registra el criterio (estado running) y lanza la evaluación en segundo plano. Regresa el stub."""
        key = _norm(criterion)
        model = await ai_model_config.get_model("criteria_refine")
        crit = {"id": str(uuid.uuid4()), "text": criterion, "key": key, "scope": scope, "model": model, "status": "running",
                "total": len(candidate_ids), "evaluated": 0, "from_cache": 0, "met": 0, "partial": 0, "cost_usd": 0.0,
                "created_at": datetime.now(timezone.utc).isoformat(), "created_by": actor, "results": {}}
        # Mismo criterio repetido: se reemplaza (no se acumula dos veces)
        await self.db.job_ai_refinements.update_one({"job_id": job["id"]}, {"$pull": {"criteria": {"key": key}}})
        await self.db.job_ai_refinements.update_one(
            {"job_id": job["id"]},
            {"$push": {"criteria": crit}, "$set": {"updated_at": crit["created_at"]}, "$setOnInsert": {"job_id": job["id"]}},
            upsert=True)
        asyncio.create_task(self._run(job["id"], crit, candidate_ids, model, on_done))
        return {k: v for k, v in crit.items() if k != "results"}

    async def _run(self, job_id: str, crit: Dict, candidate_ids: List[str], model: str, on_done) -> None:
        try:
            cands = await self.db.candidates.find({"id": {"$in": candidate_ids}, "is_deleted": {"$ne": True}},
                                                  {"_id": 0, "embedding": 0}).to_list(len(candidate_ids))
            order = {cid: i for i, cid in enumerate(candidate_ids)}
            cands.sort(key=lambda c: order.get(c["id"], 10**6))
            sem = asyncio.Semaphore(MAX_PARALLEL)
            results, done, cost, cached = {}, 0, 0.0, 0

            async def one(c):
                nonlocal done, cost, cached
                e = await self.evaluate_one(model, crit["text"], c, sem)
                results[c["id"]] = {k: e.get(k) for k in ("status", "quote", "company", "period", "reason", "no_evidence", "from_cache")}
                done += 1
                cost += e.get("cost_usd") or 0
                cached += 1 if e.get("from_cache") else 0
                if done % 5 == 0 or done == len(cands):
                    await self.db.job_ai_refinements.update_one(
                        {"job_id": job_id, "criteria.id": crit["id"]},
                        {"$set": {"criteria.$.evaluated": done, "criteria.$.cost_usd": round(cost, 4)}})

            await asyncio.gather(*[one(c) for c in cands])
            final = {"status": "done", "evaluated": done, "from_cache": cached, "cost_usd": round(cost, 4),
                     "met": sum(1 for e in results.values() if e.get("status") == "cumple"),
                     "partial": sum(1 for e in results.values() if e.get("status") == "parcial"),
                     "results": results, "finished_at": datetime.now(timezone.utc).isoformat()}
            await self.db.job_ai_refinements.update_one(
                {"job_id": job_id, "criteria.id": crit["id"]},
                {"$set": {f"criteria.$.{k}": v for k, v in final.items()}})
            if on_done:
                await on_done({**crit, **final})
        except Exception as e:  # noqa: BLE001
            logger.error("Afinar IA falló (%s): %s", crit.get("text"), e)
            await self.db.job_ai_refinements.update_one(
                {"job_id": job_id, "criteria.id": crit["id"]},
                {"$set": {"criteria.$.status": "error", "criteria.$.error": str(e)[:200]}})

    # ------------------------------------------------------------------ persistencia
    async def get(self, job_id: str) -> Dict:
        doc = await self.db.job_ai_refinements.find_one({"job_id": job_id}, {"_id": 0})
        return doc or {"job_id": job_id, "criteria": []}

    async def remove(self, job_id: str, criterion_id: str) -> None:
        await self.db.job_ai_refinements.update_one({"job_id": job_id}, {"$pull": {"criteria": {"id": criterion_id}}})

    async def estimate(self, total_candidates: int) -> Dict:
        model = await ai_model_config.get_model("criteria_refine")
        avg_chars = await average_cv_chars(self.db)
        per_in = min(avg_chars, MAX_CV_CHARS) // 4 + 400
        return {"model": model, "candidates": total_candidates, "avg_cv_chars": avg_chars,
                "estimated_cost_usd": round(estimate_cost_usd(model, per_in, 120) * total_candidates, 2),
                "estimated_minutes": round(total_candidates * 2.5 / MAX_PARALLEL / 60, 1)}

    # ------------------------------------------------------------------ lista unificada (Fase 4)
    @staticmethod
    def unify(v3_results: List[Dict], criteria: List[Dict]) -> List[Dict]:
        """Capa 1 (v3) + capa 2 (criterios IA). Orden: criterios cumplidos → HMS. Explica subidas."""
        rows = []
        criteria = [c for c in criteria if c.get("status", "done") == "done"]
        for i, r in enumerate(v3_results):
            cid = r.get("candidate_id")
            statuses, score, reasons = {}, 0.0, []
            for crit in criteria:
                ev = (crit.get("results") or {}).get(cid)
                if not ev:
                    continue
                statuses[crit["id"]] = {"status": ev.get("status"), "quote": ev.get("quote"), "company": ev.get("company"),
                                        "period": ev.get("period"), "no_evidence": ev.get("no_evidence")}
                score += STATUS_SCORE.get(ev.get("status"), 0.0)
                if ev.get("status") == "cumple":
                    where = ", ".join(filter(None, [ev.get("company"), ev.get("period")]))
                    reasons.append(f"{crit['text']}" + (f" en {where}" if where else ""))
            rows.append({**r, "v3_rank": i + 1, "ai_criteria": statuses, "ai_score": score,
                         "ai_met": sum(1 for s in statuses.values() if s["status"] == "cumple"),
                         "ai_partial": sum(1 for s in statuses.values() if s["status"] == "parcial"), "_reasons": reasons})
        rows.sort(key=lambda x: (-x["ai_score"], -(x.get("match_score_v3") or 0), x["v3_rank"]))
        for pos, row in enumerate(rows, 1):
            row["rank"] = pos
            reasons = row.pop("_reasons")
            row["moved_up_by"] = f"subió por: {'; '.join(reasons)}" if pos < row["v3_rank"] and reasons else None
        return rows

    async def coverage(self, job: Dict) -> Dict:
        targets, requirement = job_target_industries(job)
        if not targets:
            return {"targets": [], "per_industry": {}, "any": 0, "low_coverage": False}
        cands = await self.db.candidates.find({"is_deleted": {"$ne": True}},
                                              {"_id": 0, "id": 1, "industry": 1, "current_company": 1, "current_title": 1,
                                               "current_start_date": 1, "previous_companies": 1}).to_list(10000)
        cov = coverage_by_industry(cands, targets)
        return {"targets": targets, "requirement": requirement, **cov, "total_candidates": len(cands),
                "low_coverage": cov["any"] < 3}
