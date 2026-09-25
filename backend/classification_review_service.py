"""Human review only: no parsing, LLM calls, scoring or matching."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument
from models import SeniorityLevel
from taxonomy import get_industry_by_key, get_functional_area_by_key
from humaniq_catalog import ENGINE_AREAS, resolve_area, resolve_seniority, CATALOG_VERSION


class ManualClassificationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[SeniorityLevel] = None
    presentation_area: Optional[str] = None
    presentation_subarea: Optional[str] = None
    presentation_seniority: Optional[str] = None
    years_experience: Optional[int] = Field(default=None, ge=0, le=100, strict=True)


class ManualClassificationResult(BaseModel):
    candidate_id: str
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None
    presentation_area: Optional[str] = None
    presentation_subarea: Optional[str] = None
    presentation_seniority: Optional[str] = None
    years_experience: Optional[int] = None
    saved: bool = True


def expand_presentation_fields(fields: dict, candidate: Optional[dict] = None) -> dict:
    """La UI edita la capa de presentación; el motor recibe su clave técnica."""
    values = dict(fields)
    raw_area = values.get("presentation_area") or values.get("functional_area")
    raw_subarea = values.get("presentation_subarea")
    if raw_subarea and not raw_area:
        raw_area = (candidate or {}).get("presentation_area")
    if raw_area:
        area = resolve_area(raw_area, raw_subarea)
        if area:
            values["presentation_area"] = area["presentation_area"]
            values["functional_area"] = area["engine_area"]
            if "presentation_subarea" in values or "presentation_area" in fields:
                values["presentation_subarea"] = area["presentation_subarea"]
            values["taxonomy_version"] = CATALOG_VERSION
        elif "presentation_area" in fields:
            raise HTTPException(422, "Valor fuera del catálogo: functional_area")
        # Si no resuelve y viene como functional_area (clave histórica o personalizada),
        # se deja tal cual: validate_review_values decide si existe en el catálogo.
    elif "presentation_area" in fields and fields["presentation_area"] is None:
        values["functional_area"] = None
        values["presentation_subarea"] = None

    raw_seniority = values.get("presentation_seniority") or values.get("seniority")
    if raw_seniority:
        seniority = resolve_seniority(raw_seniority)
        if not seniority:
            raise HTTPException(422, "Valor fuera del catálogo: seniority")
        values["presentation_seniority"] = seniority["presentation_seniority"]
        values["seniority"] = seniority["engine_seniority"]
    elif "presentation_seniority" in fields and fields["presentation_seniority"] is None:
        values["seniority"] = None
    return values


async def validate_review_values(db, fields):
    for field, collection, lookup in (
        ("industry", "industries", get_industry_by_key),
        ("functional_area", "functional_areas", get_functional_area_by_key),
    ):
        value = fields.get(field)
        if value is None:
            continue
        if field == "functional_area" and value in ENGINE_AREAS:
            continue
        if not lookup(value):
            custom = await db[collection].find_one({"key": value}, {"_id": 0, "key": 1})
            if not custom:
                raise HTTPException(422, f"Valor fuera del catálogo: {field}")


async def approval_problem(db, candidate):
    ai = candidate.get("ai_classification") or {}
    fields = {key: ai.get(key) or candidate.get(key) for key in ("industry", "functional_area", "seniority")}
    area_label = fields["functional_area"] or ai.get("presentation_area") or candidate.get("presentation_area")
    if fields["industry"] in (None, "") or fields["seniority"] in (None, "") or not area_label:
        return "Completa industria, área funcional y seniority antes de aprobar."
    if fields["seniority"] not in {level.value for level in SeniorityLevel}:
        return "Selecciona un seniority válido antes de aprobar."
    try:
        await validate_review_values(db, fields)
    except HTTPException as error:
        return error.detail
    return None


class PendingReviewIds(BaseModel):
    candidate_ids: list[str]
    total: int


async def save_manual_classification(db, candidate_id, patch, user_id):
    fields = patch.model_dump(exclude_unset=True, mode="json")
    if not fields:
        raise HTTPException(400, "No hay cambios para guardar")
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "presentation_area": 1, "ai_classification.approved_by_recruiter": 1},
    )
    if not candidate:
        raise HTTPException(404, "Candidato no encontrado")
    fields = expand_presentation_fields(fields, candidate)
    await validate_review_values(db, fields)
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
        projection={"_id": 0, "industry": 1, "functional_area": 1, "seniority": 1, "years_experience": 1,
                    "presentation_area": 1, "presentation_subarea": 1, "presentation_seniority": 1},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "La ficha ya fue aprobada o dejó de estar disponible. Actualiza la bandeja.")
    return ManualClassificationResult(candidate_id=candidate_id, **updated)