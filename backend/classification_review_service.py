"""Human review only: no parsing, LLM calls, scoring or matching."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument
from models import SeniorityLevel
from taxonomy import get_industry_by_key, get_functional_area_by_key


class ManualClassificationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[SeniorityLevel] = None
    years_experience: Optional[int] = Field(default=None, ge=0, le=100, strict=True)


class ManualClassificationResult(BaseModel):
    candidate_id: str
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None
    years_experience: Optional[int] = None
    saved: bool = True


class PendingReviewIds(BaseModel):
    candidate_ids: list[str]
    total: int


async def validate_review_values(db, fields):
    for field, collection, lookup in (
        ("industry", "industries", get_industry_by_key),
        ("functional_area", "functional_areas", get_functional_area_by_key),
    ):
        value = fields.get(field)
        if value is not None and not lookup(value):
            custom = await db[collection].find_one({"key": value}, {"_id": 0, "key": 1})
            if not custom:
                raise HTTPException(422, f"Valor fuera del catálogo: {field}")


async def approval_problem(db, candidate):
    ai = candidate.get("ai_classification") or {}
    fields = {key: ai.get(key) or candidate.get(key) for key in ("industry", "functional_area", "seniority")}
    if any(value is None or value == "" for value in fields.values()):
        return "Completa industria, área funcional y seniority antes de aprobar."
    if fields["seniority"] not in {level.value for level in SeniorityLevel}:
        return "Selecciona un seniority válido antes de aprobar."
    try:
        await validate_review_values(db, fields)
    except HTTPException as error:
        return error.detail
    return None


async def save_manual_classification(db, candidate_id, patch, user_id):
    fields = patch.model_dump(exclude_unset=True, mode="json")
    if not fields:
        raise HTTPException(400, "No hay cambios para guardar")
    await validate_review_values(db, fields)
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "ai_classification.approved_by_recruiter": 1},
    )
    if not candidate:
        raise HTTPException(404, "Candidato no encontrado")
    now = datetime.now(timezone.utc).isoformat()
    # Atomic merge preserves simultaneous edits, AI evidence and original confidence.
    ai_defaults = {"confidence_score": 0.0, "approved_by_recruiter": False, "source": "manual_draft", "classified_at": now}
    updated = await db.candidates.find_one_and_update(
        {"id": candidate_id, "is_deleted": {"$ne": True}, "ai_classification.approved_by_recruiter": {"$ne": True}},
        [{"$set": {
            **{key: {"$literal": value} for key, value in fields.items()},
            "updated_at": now,
            "ai_classification": {"$mergeObjects": [
                ai_defaults, {"$ifNull": ["$ai_classification", {}]},
                {"$literal": fields},
                {"was_corrected": True, "manually_edited_at": now, "manually_edited_by": user_id,
                 "manual_fields": {"$mergeObjects": [{"$ifNull": ["$ai_classification.manual_fields", {}]}, {"$literal": fields}]}}
            ]},
        }}],
        projection={"_id": 0, "industry": 1, "functional_area": 1, "seniority": 1, "years_experience": 1},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "La ficha ya fue aprobada o dejó de estar disponible. Actualiza la bandeja.")
    return ManualClassificationResult(candidate_id=candidate_id, **updated)