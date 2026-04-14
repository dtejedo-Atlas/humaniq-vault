"""
CV Version Management Service
Handles versioning, history, and comparison of candidate CVs.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CVVersionService:
    """Service for managing CV versions"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def get_next_version_number(self, candidate_id: str) -> int:
        """Get the next version number for a candidate"""
        max_version = await self.db.cv_versions.find_one(
            {"candidate_id": candidate_id},
            sort=[("version", -1)],
            projection={"version": 1}
        )
        return (max_version.get("version", 0) if max_version else 0) + 1
    
    async def create_version(
        self,
        candidate_id: str,
        file_key: str,
        file_name: str,
        file_type: str,
        uploaded_by: str,
        uploaded_by_name: str,
        upload_source: str = "manual",
        file_size: Optional[int] = None,
        parsed_snapshot: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        merged_from_candidate_id: Optional[str] = None
    ) -> Dict:
        """
        Create a new CV version for a candidate.
        Marks all previous versions as not current.
        """
        # Get next version number
        version_number = await self.get_next_version_number(candidate_id)
        
        # Mark all existing versions as not current
        await self.db.cv_versions.update_many(
            {"candidate_id": candidate_id, "is_current": True},
            {"$set": {"is_current": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Create new version
        cv_version = {
            "id": str(uuid.uuid4()),
            "candidate_id": candidate_id,
            "version": version_number,
            "file_key": file_key,
            "file_name": file_name,
            "file_type": file_type,
            "file_size": file_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by": uploaded_by,
            "uploaded_by_name": uploaded_by_name,
            "upload_source": upload_source,
            "parsed_snapshot": parsed_snapshot,
            "is_current": True,
            "is_active": True,
            "notes": notes,
            "merged_from_candidate_id": merged_from_candidate_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.cv_versions.insert_one(cv_version)
        
        logger.info(f"Created CV version {version_number} for candidate {candidate_id}")
        
        # Return without _id
        cv_version.pop("_id", None)
        return cv_version
    
    async def get_versions(self, candidate_id: str, include_inactive: bool = False) -> List[Dict]:
        """Get all CV versions for a candidate, sorted by version desc"""
        query = {"candidate_id": candidate_id}
        if not include_inactive:
            query["is_active"] = True
        
        versions = await self.db.cv_versions.find(
            query,
            {"_id": 0}
        ).sort("version", -1).to_list(100)
        
        return versions
    
    async def get_version(self, candidate_id: str, version: int) -> Optional[Dict]:
        """Get a specific version of a candidate's CV"""
        version_doc = await self.db.cv_versions.find_one(
            {"candidate_id": candidate_id, "version": version},
            {"_id": 0}
        )
        return version_doc
    
    async def get_current_version(self, candidate_id: str) -> Optional[Dict]:
        """Get the current (latest active) version of a candidate's CV"""
        version_doc = await self.db.cv_versions.find_one(
            {"candidate_id": candidate_id, "is_current": True, "is_active": True},
            {"_id": 0}
        )
        return version_doc
    
    async def compare_versions(
        self, 
        candidate_id: str, 
        version1: int, 
        version2: int
    ) -> Dict:
        """
        Compare two versions of a candidate's CV based on their parsed snapshots.
        Returns differences in key fields.
        """
        v1 = await self.get_version(candidate_id, version1)
        v2 = await self.get_version(candidate_id, version2)
        
        if not v1 or not v2:
            return {"error": "Una o ambas versiones no encontradas"}
        
        s1 = v1.get("parsed_snapshot") or {}
        s2 = v2.get("parsed_snapshot") or {}
        
        differences = []
        alerts = []
        
        # Compare key fields
        fields_to_compare = [
            ("full_name", "Nombre"),
            ("current_title", "Título actual"),
            ("current_company", "Empresa actual"),
            ("years_experience", "Años de experiencia"),
            ("industry", "Industria"),
            ("functional_area", "Área funcional"),
            ("seniority", "Seniority")
        ]
        
        for field, label in fields_to_compare:
            val1 = s1.get(field)
            val2 = s2.get(field)
            if val1 != val2:
                differences.append({
                    "field": field,
                    "label": label,
                    "version_old": val1,
                    "version_new": val2,
                    "type": "changed"
                })
        
        # Compare experiences
        exp1 = s1.get("previous_companies") or []
        exp2 = s2.get("previous_companies") or []
        
        exp1_set = {
            (e.get("company_name", "").lower(), e.get("title", "").lower())
            for e in exp1
        }
        exp2_set = {
            (e.get("company_name", "").lower(), e.get("title", "").lower())
            for e in exp2
        }
        
        # Experiences removed
        removed_exp = exp1_set - exp2_set
        if removed_exp:
            alerts.append({
                "type": "high",
                "message": f"Se eliminaron {len(removed_exp)} experiencia(s) del CV",
                "details": [f"{company} - {title}" for company, title in removed_exp]
            })
            differences.append({
                "field": "previous_companies",
                "label": "Experiencias eliminadas",
                "count": len(removed_exp),
                "type": "removed"
            })
        
        # Experiences added
        added_exp = exp2_set - exp1_set
        if added_exp:
            differences.append({
                "field": "previous_companies",
                "label": "Experiencias agregadas",
                "count": len(added_exp),
                "type": "added"
            })
        
        # Compare skills
        skills1 = set(s1.get("skills") or [])
        skills2 = set(s2.get("skills") or [])
        
        removed_skills = skills1 - skills2
        added_skills = skills2 - skills1
        
        if removed_skills:
            differences.append({
                "field": "skills",
                "label": "Skills eliminados",
                "values": list(removed_skills),
                "type": "removed"
            })
        
        if added_skills:
            differences.append({
                "field": "skills",
                "label": "Skills agregados",
                "values": list(added_skills),
                "type": "added"
            })
        
        # Compare education
        edu1 = s1.get("education") or []
        edu2 = s2.get("education") or []
        
        edu1_set = {
            (e.get("institution", "").lower(), e.get("degree", "").lower())
            for e in edu1
        }
        edu2_set = {
            (e.get("institution", "").lower(), e.get("degree", "").lower())
            for e in edu2
        }
        
        if edu1_set != edu2_set:
            differences.append({
                "field": "education",
                "label": "Educación",
                "type": "changed",
                "removed": len(edu1_set - edu2_set),
                "added": len(edu2_set - edu1_set)
            })
        
        # Check for date changes in experiences
        def get_exp_dates(exp_list):
            return {
                (e.get("company_name", "").lower(), e.get("start_date"), e.get("end_date"))
                for e in exp_list
            }
        
        # Find experiences with same company but different dates
        companies1 = {e.get("company_name", "").lower(): e for e in exp1}
        companies2 = {e.get("company_name", "").lower(): e for e in exp2}
        
        for company in set(companies1.keys()) & set(companies2.keys()):
            e1 = companies1[company]
            e2 = companies2[company]
            if e1.get("start_date") != e2.get("start_date") or e1.get("end_date") != e2.get("end_date"):
                alerts.append({
                    "type": "medium",
                    "message": f"Fechas modificadas en {company}",
                    "details": [
                        f"Antes: {e1.get('start_date')} - {e1.get('end_date')}",
                        f"Después: {e2.get('start_date')} - {e2.get('end_date')}"
                    ]
                })
        
        return {
            "version1": {
                "version": version1,
                "uploaded_at": v1.get("uploaded_at"),
                "uploaded_by_name": v1.get("uploaded_by_name")
            },
            "version2": {
                "version": version2,
                "uploaded_at": v2.get("uploaded_at"),
                "uploaded_by_name": v2.get("uploaded_by_name")
            },
            "differences": differences,
            "alerts": alerts,
            "total_differences": len(differences),
            "has_critical_alerts": any(a.get("type") == "high" for a in alerts)
        }
    
    async def soft_delete_version(self, candidate_id: str, version: int, deleted_by: str) -> bool:
        """Soft delete a CV version (for audit purposes, never hard delete)"""
        result = await self.db.cv_versions.update_one(
            {"candidate_id": candidate_id, "version": version},
            {
                "$set": {
                    "is_active": False,
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "deleted_by": deleted_by,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        if result.modified_count > 0:
            # If this was the current version, make the previous one current
            deleted_version = await self.get_version(candidate_id, version)
            if deleted_version and deleted_version.get("is_current"):
                prev_version = await self.db.cv_versions.find_one(
                    {
                        "candidate_id": candidate_id,
                        "is_active": True,
                        "version": {"$lt": version}
                    },
                    sort=[("version", -1)]
                )
                if prev_version:
                    await self.db.cv_versions.update_one(
                        {"id": prev_version["id"]},
                        {"$set": {"is_current": True}}
                    )
        
        return result.modified_count > 0
    
    async def migrate_existing_cvs(self) -> Dict:
        """
        Migrate existing CVs from candidates to cv_versions collection.
        Should be run once during deployment.
        """
        migrated = 0
        skipped = 0
        errors = 0
        
        # Get all candidates with resume_files
        candidates = await self.db.candidates.find(
            {"resume_files": {"$exists": True, "$ne": []}},
            {"_id": 0, "id": 1, "full_name": 1, "resume_files": 1, "created_at": 1,
             "current_title": 1, "current_company": 1, "years_experience": 1,
             "industry": 1, "functional_area": 1, "seniority": 1, "skills": 1,
             "previous_companies": 1, "education": 1, "created_by": 1}
        ).to_list(10000)
        
        for candidate in candidates:
            candidate_id = candidate["id"]
            
            # Check if already migrated
            existing = await self.db.cv_versions.find_one({"candidate_id": candidate_id})
            if existing:
                skipped += 1
                continue
            
            resume_files = candidate.get("resume_files") or []
            
            for idx, resume in enumerate(resume_files):
                try:
                    # Build snapshot from current candidate data
                    snapshot = {
                        "full_name": candidate.get("full_name"),
                        "current_title": candidate.get("current_title"),
                        "current_company": candidate.get("current_company"),
                        "years_experience": candidate.get("years_experience"),
                        "industry": candidate.get("industry"),
                        "functional_area": candidate.get("functional_area"),
                        "seniority": candidate.get("seniority"),
                        "skills": candidate.get("skills"),
                        "previous_companies": candidate.get("previous_companies"),
                        "education": candidate.get("education")
                    }
                    
                    version_doc = {
                        "id": str(uuid.uuid4()),
                        "candidate_id": candidate_id,
                        "version": idx + 1,
                        "file_key": resume.get("file_path"),
                        "file_name": resume.get("file_name"),
                        "file_type": resume.get("file_type"),
                        "file_size": None,
                        "uploaded_at": resume.get("upload_date") or candidate.get("created_at"),
                        "uploaded_by": candidate.get("created_by") or "system",
                        "uploaded_by_name": "Migración automática",
                        "upload_source": "migration",
                        "parsed_snapshot": snapshot if idx == len(resume_files) - 1 else None,
                        "is_current": idx == len(resume_files) - 1,  # Last one is current
                        "is_active": True,
                        "notes": "Migrado desde registro existente",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    
                    await self.db.cv_versions.insert_one(version_doc)
                    migrated += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating CV for candidate {candidate_id}: {str(e)}")
                    errors += 1
        
        logger.info(f"CV migration complete: {migrated} migrated, {skipped} skipped, {errors} errors")
        
        return {
            "migrated": migrated,
            "skipped": skipped,
            "errors": errors,
            "total_candidates": len(candidates)
        }


# Singleton instance (initialized in server.py)
cv_version_service = None
