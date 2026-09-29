"""Hashes SHA-256 de CVs: prevención de cargas repetidas y detección de CVs idénticos."""
import hashlib
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from pymongo import ASCENDING

from document_parser import DocumentParser
from text_utils import normalize_for_search

logger = logging.getLogger(__name__)

MIN_TEXT_LEN = 300
INDEX_NAME = "uniq_active_sha256_file"

# Campos escalares que se completan en la ficha conservada si están vacíos
FILL_SCALAR_FIELDS = [
    "email", "phone", "linkedin_url", "current_title", "current_company",
    "industry", "functional_area", "presentation_area", "presentation_subarea",
    "seniority", "years_experience", "city", "state", "country", "ai_summary",
]
FILL_LIST_FIELDS = ["skills", "languages", "previous_companies", "tags"]


def compute_hashes(file_data: bytes, file_type: Optional[str] = None, text: Optional[str] = None) -> Dict:
    """SHA-256 del archivo y del texto extraído normalizado (solo si tiene >= 300 chars)."""
    if text is None:
        try:
            text = DocumentParser.extract_text_from_bytes(file_data, file_type or "") or ""
        except Exception as e:
            logger.warning("No se pudo extraer texto para hash: %s", type(e).__name__)
            text = ""
    norm = normalize_for_search(text)
    return {
        "sha256_file": hashlib.sha256(file_data).hexdigest(),
        "sha256_text": hashlib.sha256(norm.encode()).hexdigest() if len(norm) >= MIN_TEXT_LEN else None,
        "text_len": len(norm),
        "size": len(file_data),
    }


class CVHashService:
    def __init__(self, db):
        self.db = db

    async def ensure_indexes(self) -> Dict:
        """Índice único global sobre sha256_file de CVs activos. Falla si aún hay duplicados."""
        try:
            await self.db.cv_hashes.create_index(
                [("sha256_file", ASCENDING)],
                name=INDEX_NAME,
                unique=True,
                partialFilterExpression={"active": True},
            )
            return {"created": True}
        except Exception as e:
            logger.warning("Índice único de hashes no creado (duplicados pendientes): %s", str(e)[:200])
            return {"created": False, "reason": str(e)[:300]}

    async def find_owner(self, sha256_file: str) -> Optional[Dict]:
        """Devuelve el CV activo que ya tiene ese hash de archivo, con el nombre del candidato."""
        doc = await self.db.cv_hashes.find_one(
            {"sha256_file": sha256_file, "active": True}, {"_id": 0}
        )
        if not doc:
            return None
        candidate = await self.db.candidates.find_one(
            {"id": doc["candidate_id"], "is_deleted": {"$ne": True}},
            {"_id": 0, "id": 1, "full_name": 1},
        )
        if not candidate:
            # La ficha fue eliminada: el hash ya no bloquea.
            await self.db.cv_hashes.update_one(
                {"candidate_id": doc["candidate_id"], "file_path": doc["file_path"]},
                {"$set": {"active": False}},
            )
            return None
        return {
            "candidate_id": candidate["id"],
            "candidate_name": candidate.get("full_name"),
            "file_name": doc.get("file_name"),
            "upload_date": doc.get("upload_date"),
        }

    async def register(
        self, candidate_id: str, candidate_name: Optional[str], file_path: str,
        file_name: str, file_type: Optional[str], uploaded_by: Optional[str],
        hashes: Dict, upload_date: Optional[str] = None,
    ) -> None:
        """Registra el hash de un CV recién almacenado. Puede lanzar DuplicateKeyError."""
        await self.db.cv_hashes.insert_one({
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "file_path": file_path,
            "file_name": file_name,
            "file_type": file_type,
            "uploaded_by": uploaded_by,
            "upload_date": upload_date or datetime.now(timezone.utc).isoformat(),
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
            **hashes,
        })

    async def deactivate_candidate(self, candidate_id: str) -> int:
        result = await self.db.cv_hashes.update_many(
            {"candidate_id": candidate_id, "active": True}, {"$set": {"active": False}}
        )
        return result.modified_count

    async def reactivate_candidate(self, candidate_id: str) -> int:
        """Al restaurar una ficha, reactiva sus hashes salvo que otro CV activo ya tenga el mismo."""
        reactivated = 0
        docs = await self.db.cv_hashes.find(
            {"candidate_id": candidate_id, "active": False}, {"_id": 0, "file_path": 1}
        ).to_list(length=None)
        for doc in docs:
            try:
                await self.db.cv_hashes.update_one(
                    {"candidate_id": candidate_id, "file_path": doc["file_path"]},
                    {"$set": {"active": True}},
                )
                reactivated += 1
            except Exception:
                logger.info("Hash de %s no reactivado: ya existe un CV activo idéntico", candidate_id)
        return reactivated

    async def transfer_candidate(self, from_id: str, to_id: str) -> Dict:
        """Tras una fusión, los hashes del secundario pasan al primario (o se desactivan si ya existen)."""
        moved, deactivated = 0, 0
        docs = await self.db.cv_hashes.find(
            {"candidate_id": from_id, "active": True}, {"_id": 0, "file_path": 1}
        ).to_list(length=None)
        for doc in docs:
            try:
                await self.db.cv_hashes.update_one(
                    {"candidate_id": from_id, "file_path": doc["file_path"]},
                    {"$set": {"candidate_id": to_id}},
                )
                moved += 1
            except Exception:
                await self.db.cv_hashes.update_one(
                    {"candidate_id": from_id, "file_path": doc["file_path"]},
                    {"$set": {"active": False}},
                )
                deactivated += 1
        return {"moved": moved, "deactivated": deactivated}

    async def identical_groups(self) -> List[Dict]:
        """Agrupa fichas cuyo CV es idéntico (mismo hash de archivo o de texto normalizado)."""
        rows = await self.db.cv_hashes.find(
            {"active": True, "error": {"$exists": False}}, {"_id": 0}
        ).to_list(length=None)

        parent = {r["file_path"]: r["file_path"] for r in rows}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        buckets = {}
        for r in rows:
            buckets.setdefault(("f", r["sha256_file"]), []).append(r["file_path"])
            if r.get("sha256_text"):
                buckets.setdefault(("t", r["sha256_text"]), []).append(r["file_path"])
        for paths in buckets.values():
            root = find(paths[0])
            for p in paths[1:]:
                other = find(p)
                if other != root:
                    parent[other] = root

        grouped: Dict[str, List[Dict]] = {}
        for r in rows:
            grouped.setdefault(find(r["file_path"]), []).append(r)

        candidate_ids = {r["candidate_id"] for r in rows}
        candidates = {
            c["id"]: c for c in await self.db.candidates.find(
                {"id": {"$in": list(candidate_ids)}, "is_deleted": {"$ne": True}}, {"_id": 0, "embedding": 0}
            ).to_list(length=None)
        }
        users = {
            u["id"]: u.get("name") or u.get("email")
            for u in await self.db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(length=None)
        }
        assignment_counts: Dict[str, int] = {}
        for a in await self.db.assignments.find({}, {"_id": 0, "candidate_id": 1}).to_list(length=None):
            cid = a.get("candidate_id")
            assignment_counts[cid] = assignment_counts.get(cid, 0) + 1
        version_counts: Dict[str, int] = {}
        for v in await self.db.cv_versions.find({}, {"_id": 0, "candidate_id": 1}).to_list(length=None):
            cid = v.get("candidate_id")
            version_counts[cid] = version_counts.get(cid, 0) + 1

        groups = []
        for key, files in grouped.items():
            members = []
            for cid in sorted({f["candidate_id"] for f in files}):
                c = candidates.get(cid)
                if not c:
                    continue
                own_files = [f for f in files if f["candidate_id"] == cid]
                notes = c.get("notes")
                note_count = len(notes) if isinstance(notes, list) else (1 if notes else 0)
                classification = c.get("ai_classification") or {}
                members.append({
                    "candidate_id": cid,
                    "name": c.get("full_name"),
                    "name_norm": normalize_for_search(c.get("full_name") or ""),
                    "created_at": c.get("created_at"),
                    "uploaded_by": users.get(c.get("created_by"), c.get("created_by")),
                    "upload_date": min([f.get("upload_date") or "" for f in own_files]) or None,
                    "file_names": [f.get("file_name") for f in own_files],
                    "notes": note_count,
                    "assignments": assignment_counts.get(cid, 0),
                    "cv_versions": version_counts.get(cid, 0),
                    "resume_files": len(c.get("resume_files") or []),
                    "approved_classification": bool(classification.get("approved_by_recruiter")),
                    "skills": len(c.get("skills") or []),
                    "presentation_subarea": c.get("presentation_subarea"),
                })
            if len(members) < 2:
                continue

            members.sort(key=lambda m: m["created_at"] or "")
            approved = [m for m in members if m["approved_classification"]]
            keep = approved[0] if approved else members[0]
            extras = [m for m in members if m["candidate_id"] != keep["candidate_id"]]

            base = keep["name_norm"]
            distinct_names = any(
                SequenceMatcher(None, base, m["name_norm"]).ratio() < 0.6 for m in extras
            )
            needs_merge = any(
                m["notes"] or m["assignments"] or m["cv_versions"] or m["resume_files"] > 1
                for m in extras
            )
            if distinct_names:
                status = "manual_review"
            elif needs_merge:
                status = "merge_required"
            else:
                status = "safe"

            groups.append({
                "group_key": min(f["file_path"] for f in files),
                "file_paths": sorted(f["file_path"] for f in files),
                "status": status,
                "match": "file" if len({f["sha256_file"] for f in files}) == 1 else "text",
                "keep": keep,
                "extras": extras,
            })

        order = {"safe": 0, "merge_required": 1, "manual_review": 2}
        groups.sort(key=lambda g: (order[g["status"]], -len(g["extras"])))
        return groups

    async def fill_missing_from_extras(self, keep_id: str, extra_ids: List[str]) -> Dict:
        """Copia a la ficha conservada los datos que le falten y estén en las sobrantes."""
        keep = await self.db.candidates.find_one({"id": keep_id}, {"_id": 0, "embedding": 0})
        if not keep:
            return {}
        updates: Dict = {}
        for eid in extra_ids:
            extra = await self.db.candidates.find_one({"id": eid}, {"_id": 0, "embedding": 0})
            if not extra:
                continue
            for field in FILL_SCALAR_FIELDS:
                current = updates.get(field, keep.get(field))
                if not current and extra.get(field):
                    updates[field] = extra[field]
            for field in FILL_LIST_FIELDS:
                current = updates.get(field, keep.get(field)) or []
                incoming = extra.get(field) or []
                if not isinstance(current, list) or not isinstance(incoming, list):
                    continue
                merged = list(current)
                seen = {str(v).casefold() for v in current if not isinstance(v, dict)}
                for item in incoming:
                    if isinstance(item, dict):
                        if item not in merged:
                            merged.append(item)
                    elif str(item).casefold() not in seen:
                        merged.append(item)
                        seen.add(str(item).casefold())
                if len(merged) > len(current):
                    updates[field] = merged
        if updates:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self.db.candidates.update_one({"id": keep_id}, {"$set": updates})
            updates.pop("updated_at")
        return updates
