"""Texto completo de CVs con caché en Mongo (`cv_fulltext`), clave por (candidato, archivo vigente)."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from cv_recheck_service import current_resume, download_original
from document_parser import DocumentParser

logger = logging.getLogger(__name__)


def _extract(raw: bytes, file_type: str) -> str:
    details = DocumentParser.extract_with_details(raw, file_type or "pdf")
    return (details.get("text") or "").strip()


async def get_cv_text(db, candidate: Dict) -> Dict:
    """Devuelve {"text", "cv_key", "cached"}; text vacío si no hay CV o no se pudo extraer."""
    try:
        ref = await current_resume(db, candidate)
    except ValueError:
        return {"text": "", "cv_key": None, "cached": False}
    key = ref.get("key")
    cached = await db.cv_fulltext.find_one({"candidate_id": candidate["id"], "cv_key": key}, {"_id": 0})
    if cached and cached.get("text"):
        return {"text": cached["text"], "cv_key": key, "cached": True}
    try:
        raw = await asyncio.to_thread(download_original, ref)
        text = await asyncio.to_thread(_extract, raw, ref.get("type"))
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo extraer texto del CV %s: %s", candidate.get("id"), e)
        text = ""
    await db.cv_fulltext.update_one(
        {"candidate_id": candidate["id"], "cv_key": key},
        {"$set": {"candidate_id": candidate["id"], "cv_key": key, "text": text, "chars": len(text),
                  "extracted_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"text": text, "cv_key": key, "cached": False}


async def average_cv_chars(db, sample: int = 200) -> int:
    docs = await db.cv_fulltext.find({"chars": {"$gt": 0}}, {"_id": 0, "chars": 1}).limit(sample).to_list(sample)
    if not docs:
        return 6000
    return int(sum(d["chars"] for d in docs) / len(docs))
