"""Ciclo de vida de vacantes: última actividad, caducidad a 90 días, archivo y reutilización."""
import logging
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ARCHIVE_AFTER_DAYS = 90
WARN_BEFORE_DAYS = 7


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


class JobLifecycleService:
    def __init__(self, db):
        self.db = db

    async def last_activity_map(self) -> Dict[str, datetime]:
        """Última actividad por vacante: logs de actividad y movimientos de asignaciones."""
        result: Dict[str, datetime] = {}
        async for row in self.db.activity_logs.aggregate([
            {"$match": {"entity_type": "job"}},
            {"$group": {"_id": "$entity_id", "last": {"$max": "$timestamp"}}},
        ]):
            dt = _parse_dt(row.get("last"))
            if dt:
                result[row["_id"]] = dt
        async for row in self.db.candidates.aggregate([
            {"$match": {"is_deleted": {"$ne": True}, "job_assignments.0": {"$exists": True}}},
            {"$unwind": "$job_assignments"},
            {"$group": {"_id": "$job_assignments.job_id", "last": {"$max": "$job_assignments.updated_at"}}},
        ]):
            dt = _parse_dt(row.get("last"))
            if dt and (row["_id"] not in result or dt > result[row["_id"]]):
                result[row["_id"]] = dt
        return result

    async def inactivity_report(self) -> Dict:
        """Vacantes activas por caducar (aviso 7 días antes) y ya caducadas (>= 90 días)."""
        now = datetime.now(timezone.utc)
        activity = await self.last_activity_map()
        jobs = await self.db.jobs.find(
            {"status": {"$nin": ["archived", "closed"]}}, {"_id": 0, "embedding": 0}
        ).to_list(500)

        expiring, expired = [], []
        for job in jobs:
            dates = [activity.get(job["id"]), _parse_dt(job.get("last_activity_at")),
                     _parse_dt(job.get("updated_at")), _parse_dt(job.get("created_at"))]
            last = max([d for d in dates if d], default=None)
            days_inactive = (now - last).days if last else ARCHIVE_AFTER_DAYS
            item = {
                "id": job["id"],
                "title": job.get("title"),
                "company": job.get("company"),
                "days_inactive": days_inactive,
                "days_until_archive": max(ARCHIVE_AFTER_DAYS - days_inactive, 0),
                "last_activity_at": last.isoformat() if last else None,
            }
            if days_inactive >= ARCHIVE_AFTER_DAYS:
                expired.append(item)
            elif days_inactive >= ARCHIVE_AFTER_DAYS - WARN_BEFORE_DAYS:
                expiring.append(item)

        expiring.sort(key=lambda x: -x["days_inactive"])
        expired.sort(key=lambda x: -x["days_inactive"])
        return {
            "expiring": expiring,
            "expired": expired,
            "archive_after_days": ARCHIVE_AFTER_DAYS,
            "warn_before_days": WARN_BEFORE_DAYS,
        }

    async def archive(self, job_id: str, actor: str, reason: Optional[str] = None, auto: bool = False) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        result = await self.db.jobs.update_one(
            {"id": job_id, "status": {"$ne": "archived"}},
            {"$set": {
                "status": "archived",
                "archived_at": now,
                "archived_by": actor,
                "archive_reason": reason or ("Caducidad automática por 90 días sin actividad" if auto else None),
                "auto_archived": auto,
                "updated_at": now,
            }}
        )
        return result.modified_count > 0

    async def reactivate(self, job_id: str, actor: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        result = await self.db.jobs.update_one(
            {"id": job_id, "status": "archived"},
            {
                "$set": {"status": "active", "last_activity_at": now, "updated_at": now, "reactivated_by": actor},
                "$unset": {"archived_at": "", "archived_by": "", "archive_reason": "", "auto_archived": ""},
            }
        )
        return result.modified_count > 0

    async def auto_archive(self) -> List[Dict]:
        """Archiva las vacantes con 90 días o más sin actividad."""
        report = await self.inactivity_report()
        archived = []
        for job in report["expired"]:
            if await self.archive(job["id"], actor="system", auto=True):
                archived.append(job)
        if archived:
            logger.info("Auto-archivadas %s vacantes por inactividad", len(archived))
        return archived

    async def similar_archived(
        self, title: Optional[str] = None, presentation_area: Optional[str] = None,
        presentation_subarea: Optional[str] = None, functional_area: Optional[str] = None,
        exclude_job_id: Optional[str] = None, limit: int = 5,
    ) -> List[Dict]:
        """Vacantes archivadas parecidas (mismo título o misma área/subárea) con sus candidatos."""
        archived = await self.db.jobs.find(
            {"status": "archived"}, {"_id": 0, "embedding": 0}
        ).to_list(300)

        title_norm = _norm(title)
        matches = []
        for job in archived:
            if exclude_job_id and job["id"] == exclude_job_id:
                continue
            reasons = []
            if title_norm:
                ratio = SequenceMatcher(None, title_norm, _norm(job.get("title"))).ratio()
                if ratio >= 0.7:
                    reasons.append("Mismo título")
            if presentation_subarea and job.get("presentation_subarea") == presentation_subarea:
                reasons.append("Misma subárea")
            if presentation_area and job.get("presentation_area") == presentation_area:
                reasons.append("Misma área")
            if not reasons and functional_area and job.get("functional_area") == functional_area:
                reasons.append("Misma área técnica")
            if not reasons:
                continue
            matches.append({
                "id": job["id"],
                "title": job.get("title"),
                "company": job.get("company"),
                "archived_at": job.get("archived_at"),
                "presentation_area": job.get("presentation_area"),
                "presentation_subarea": job.get("presentation_subarea"),
                "match_reasons": reasons,
                "candidates": [],
            })

        matches.sort(key=lambda m: (-len(m["match_reasons"]), str(m.get("archived_at") or "")))
        matches = matches[:limit]

        for match in matches:
            async for cand in self.db.candidates.find(
                {"is_deleted": {"$ne": True}, "job_assignments.job_id": match["id"]},
                {"_id": 0, "id": 1, "full_name": 1, "current_title": 1, "current_company": 1, "job_assignments": 1},
            ):
                stage = next((a.get("stage") for a in cand.get("job_assignments", [])
                              if a.get("job_id") == match["id"]), None)
                match["candidates"].append({
                    "id": cand["id"],
                    "full_name": cand.get("full_name"),
                    "current_title": cand.get("current_title"),
                    "current_company": cand.get("current_company"),
                    "stage": stage,
                })
        return matches
