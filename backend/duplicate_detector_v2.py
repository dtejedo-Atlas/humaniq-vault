"""
Duplicate Detection and Merge System v2
- Hard blocking for L1 (email) and L2 (linkedin)
- Soft suggestions for L3-L5
- Manual merge with audit trail
- CV version management foundation
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import re
import uuid
from difflib import SequenceMatcher
import logging
import unicodedata

logger = logging.getLogger(__name__)


class DuplicateDetectorV2:
    """Enhanced duplicate detection with hard blocking and soft suggestions"""
    
    def __init__(self, db):
        self.db = db
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison: lowercase, remove accents, extra spaces"""
        if not text:
            return ""
        # Remove accents
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        # Lowercase and normalize spaces
        return ' '.join(text.lower().split())
    
    @staticmethod
    def normalize_email(email: str) -> str:
        """Normalize email for comparison"""
        if not email:
            return ""
        email = email.lower().strip()
        # Remove dots before @ for gmail-style addresses
        local, _, domain = email.partition('@')
        if domain in ['gmail.com', 'googlemail.com']:
            local = local.replace('.', '')
        return f"{local}@{domain}" if domain else email
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number for comparison"""
        if not phone:
            return ""
        digits = re.sub(r'\D', '', phone)
        # Remove Mexico country code
        if digits.startswith('52') and len(digits) > 10:
            digits = digits[2:]
        # Remove leading 1 for US numbers
        if digits.startswith('1') and len(digits) == 11:
            digits = digits[1:]
        return digits if len(digits) >= 10 else ""
    
    @staticmethod
    def normalize_linkedin(url: str) -> str:
        """Normalize LinkedIn URL for comparison"""
        if not url:
            return ""
        patterns = [
            r'linkedin\.com/in/([^/?#]+)',
            r'linkedin\.com/pub/([^/?#]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url.lower())
            if match:
                return match.group(1).strip('/')
        return ""
    
    @staticmethod
    def name_similarity(name1: str, name2: str) -> float:
        """Calculate similarity between two names (0.0 to 1.0)"""
        if not name1 or not name2:
            return 0.0
        n1 = DuplicateDetectorV2.normalize_text(name1)
        n2 = DuplicateDetectorV2.normalize_text(name2)
        return SequenceMatcher(None, n1, n2).ratio()
    
    @staticmethod
    def get_common_companies(companies1: List[Dict], companies2: List[Dict]) -> List[str]:
        """Find common companies between two candidate histories"""
        if not companies1 or not companies2:
            return []
        
        def normalize_company(name):
            if not name:
                return ""
            # Remove common suffixes
            name = re.sub(r'\b(s\.?a\.?|s\.?a\.?\s*de\s*c\.?v\.?|inc\.?|llc|ltd|corp\.?)\b', '', name.lower())
            return DuplicateDetectorV2.normalize_text(name)
        
        names1 = {normalize_company(c.get('company_name', '')) for c in companies1 if c.get('company_name')}
        names2 = {normalize_company(c.get('company_name', '')) for c in companies2 if c.get('company_name')}
        names1.discard("")
        names2.discard("")
        
        return list(names1.intersection(names2))
    
    async def detect_hard_duplicates(self, candidate_data: dict, exclude_id: str = None) -> Optional[Dict]:
        """
        Detect L1/L2 duplicates that should be BLOCKED.
        Returns the existing candidate if found, None otherwise.
        """
        query_base = {"$or": [{"is_deleted": False}, {"is_deleted": {"$exists": False}}]}
        if exclude_id:
            query_base["id"] = {"$ne": exclude_id}
        
        # L1: Email match (100% confidence) - HARD BLOCK
        if email := candidate_data.get('email'):
            normalized_email = self.normalize_email(email)
            if normalized_email:
                # Find all candidates and check normalized email
                all_with_email = await self.db.candidates.find(
                    {**query_base, "email": {"$ne": None}},
                    {"_id": 0, "id": 1, "full_name": 1, "email": 1, "current_title": 1, 
                     "current_company": 1, "created_at": 1, "years_experience": 1}
                ).to_list(5000)
                
                for candidate in all_with_email:
                    if self.normalize_email(candidate.get('email', '')) == normalized_email:
                        return {
                            "candidate_id": candidate['id'],
                            "candidate_name": candidate.get('full_name'),
                            "candidate_email": candidate.get('email'),
                            "candidate_title": candidate.get('current_title'),
                            "candidate_company": candidate.get('current_company'),
                            "match_type": "email",
                            "confidence": 1.0,
                            "reason": "Email idéntico encontrado",
                            "block_level": "L1"
                        }
        
        # L2: LinkedIn match (95% confidence) - HARD BLOCK
        if linkedin := candidate_data.get('linkedin_url'):
            normalized_linkedin = self.normalize_linkedin(linkedin)
            if normalized_linkedin:
                all_with_linkedin = await self.db.candidates.find(
                    {**query_base, "linkedin_url": {"$ne": None}},
                    {"_id": 0, "id": 1, "full_name": 1, "linkedin_url": 1, "current_title": 1, "current_company": 1}
                ).to_list(5000)
                
                for candidate in all_with_linkedin:
                    if self.normalize_linkedin(candidate.get('linkedin_url', '')) == normalized_linkedin:
                        return {
                            "candidate_id": candidate['id'],
                            "candidate_name": candidate.get('full_name'),
                            "candidate_linkedin": candidate.get('linkedin_url'),
                            "candidate_title": candidate.get('current_title'),
                            "candidate_company": candidate.get('current_company'),
                            "match_type": "linkedin",
                            "confidence": 0.95,
                            "reason": "Perfil de LinkedIn idéntico",
                            "block_level": "L2"
                        }
        
        return None
    
    async def detect_soft_duplicates(self, candidate_data: dict, exclude_id: str = None) -> List[Dict]:
        """
        Detect L3-L5 duplicates that should be SUGGESTED for review.
        Returns list of potential matches sorted by confidence.
        """
        matches = []
        query_base = {"$or": [{"is_deleted": False}, {"is_deleted": {"$exists": False}}]}
        if exclude_id:
            query_base["id"] = {"$ne": exclude_id}
        
        full_name = candidate_data.get('full_name', '')
        phone = candidate_data.get('phone', '')
        normalized_phone = self.normalize_phone(phone)
        
        # Get all candidates for comparison
        all_candidates = await self.db.candidates.find(
            query_base,
            {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1,
             "previous_companies": 1, "current_title": 1, "current_company": 1,
             "industry": 1, "years_experience": 1}
        ).to_list(5000)
        
        for candidate in all_candidates:
            name_sim = self.name_similarity(full_name, candidate.get('full_name', ''))
            
            # L3: Phone match + name similar (92% confidence)
            if normalized_phone and len(normalized_phone) >= 10:
                cand_phone = self.normalize_phone(candidate.get('phone', ''))
                if cand_phone == normalized_phone and name_sim >= 0.80:
                    matches.append({
                        "candidate_id": candidate['id'],
                        "candidate_name": candidate.get('full_name'),
                        "candidate_email": candidate.get('email'),
                        "candidate_title": candidate.get('current_title'),
                        "candidate_company": candidate.get('current_company'),
                        "match_type": "phone_name",
                        "confidence": 0.92,
                        "reason": f"Teléfono idéntico + nombre similar ({int(name_sim*100)}%)",
                        "block_level": "L3"
                    })
                    continue
            
            # L4: Name identical + common companies (88% confidence)
            if name_sim >= 0.95:
                common_companies = self.get_common_companies(
                    candidate_data.get('previous_companies', []),
                    candidate.get('previous_companies', [])
                )
                if len(common_companies) >= 2:
                    matches.append({
                        "candidate_id": candidate['id'],
                        "candidate_name": candidate.get('full_name'),
                        "candidate_email": candidate.get('email'),
                        "candidate_title": candidate.get('current_title'),
                        "candidate_company": candidate.get('current_company'),
                        "match_type": "name_companies",
                        "confidence": 0.88,
                        "reason": f"Nombre casi idéntico + trabajó en: {', '.join(common_companies[:3])}",
                        "block_level": "L4"
                    })
                    continue
            
            # L5: Name very similar + same industry + similar experience (75% confidence)
            if name_sim >= 0.90:
                same_industry = candidate_data.get('industry') == candidate.get('industry')
                years_diff = abs((candidate_data.get('years_experience') or 0) - (candidate.get('years_experience') or 0))
                similar_years = years_diff <= 3
                
                if same_industry and similar_years:
                    matches.append({
                        "candidate_id": candidate['id'],
                        "candidate_name": candidate.get('full_name'),
                        "candidate_email": candidate.get('email'),
                        "candidate_title": candidate.get('current_title'),
                        "candidate_company": candidate.get('current_company'),
                        "match_type": "name_profile",
                        "confidence": 0.75,
                        "reason": f"Nombre muy similar ({int(name_sim*100)}%) + misma industria + experiencia similar",
                        "block_level": "L5"
                    })
        
        # Sort by confidence and return top matches
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches[:10]
    
    async def get_all_duplicate_groups(self) -> List[Dict]:
        """
        Scan the entire database and return groups of duplicate candidates.
        Used for the admin duplicate review panel.
        """
        query = {"$or": [{"is_deleted": False}, {"is_deleted": {"$exists": False}}, {"is_deleted": None}]}
        all_candidates = await self.db.candidates.find(
            query,
            {"_id": 0, "id": 1, "full_name": 1, "email": 1, "phone": 1, 
             "linkedin_url": 1, "current_title": 1, "current_company": 1,
             "created_at": 1, "years_experience": 1, "industry": 1}
        ).to_list(10000)
        
        # Group by normalized email (case-insensitive)
        email_groups = {}
        for c in all_candidates:
            if email := c.get('email'):
                norm_email = email.lower().strip()
                if norm_email:
                    if norm_email not in email_groups:
                        email_groups[norm_email] = []
                    email_groups[norm_email].append(c)
        
        # Find groups with duplicates
        duplicate_groups = []
        processed_ids = set()
        
        for email, candidates in email_groups.items():
            if len(candidates) > 1:
                ids = [c['id'] for c in candidates]
                if not any(id in processed_ids for id in ids):
                    processed_ids.update(ids)
                    duplicate_groups.append({
                        "group_id": str(uuid.uuid4()),
                        "match_type": "email",
                        "match_value": email,
                        "confidence": 1.0,
                        "candidates": candidates,
                        "count": len(candidates)
                    })
        
        # Group by normalized phone
        phone_groups = {}
        for c in all_candidates:
            if c['id'] in processed_ids:
                continue
            if phone := c.get('phone'):
                norm_phone = self.normalize_phone(phone)
                if norm_phone and len(norm_phone) >= 10:
                    if norm_phone not in phone_groups:
                        phone_groups[norm_phone] = []
                    phone_groups[norm_phone].append(c)
        
        for phone, candidates in phone_groups.items():
            if len(candidates) > 1:
                # Check if names are similar
                names = [c.get('full_name', '') for c in candidates]
                if len(names) >= 2:
                    sim = self.name_similarity(names[0], names[1])
                    if sim >= 0.70:
                        ids = [c['id'] for c in candidates]
                        processed_ids.update(ids)
                        duplicate_groups.append({
                            "group_id": str(uuid.uuid4()),
                            "match_type": "phone",
                            "match_value": phone,
                            "confidence": 0.90,
                            "candidates": candidates,
                            "count": len(candidates)
                        })
        
        # Sort by confidence then by count
        duplicate_groups.sort(key=lambda x: (-x['confidence'], -x['count']))
        
        return duplicate_groups


class CandidateMerger:
    """Handle manual merge of duplicate candidates with audit trail"""
    
    def __init__(self, db):
        self.db = db
    
    async def merge_candidates(
        self, 
        primary_id: str, 
        secondary_id: str, 
        merge_options: Dict,
        merged_by: str
    ) -> Dict:
        """
        Merge two candidate records.
        
        Args:
            primary_id: ID of the candidate to keep as primary
            secondary_id: ID of the candidate to merge into primary
            merge_options: Dict specifying what to merge:
                - merge_experience: bool - Combine work history
                - merge_education: bool - Combine education
                - merge_skills: bool - Combine skills
                - merge_notes: bool - Combine notes
                - keep_all_cvs: bool - Keep CVs from both
                - use_secondary_contact: bool - Use contact info from secondary
            merged_by: User ID performing the merge
        
        Returns:
            Dict with merge result and audit info
        """
        # Get both candidates
        primary = await self.db.candidates.find_one({"id": primary_id})
        secondary = await self.db.candidates.find_one({"id": secondary_id})
        
        if not primary or not secondary:
            raise ValueError("One or both candidates not found")
        
        # Build merged data
        merged_data = {}
        merge_log = []
        
        # Contact info
        if merge_options.get('use_secondary_contact'):
            if secondary.get('email'):
                merged_data['email'] = secondary['email']
                merge_log.append(f"Email actualizado: {secondary['email']}")
            if secondary.get('phone'):
                merged_data['phone'] = secondary['phone']
                merge_log.append(f"Teléfono actualizado: {secondary['phone']}")
        
        # Merge experience (combine both)
        if merge_options.get('merge_experience'):
            primary_exp = primary.get('previous_companies', []) or []
            secondary_exp = secondary.get('previous_companies', []) or []
            
            # Deduplicate by company name + title + dates
            combined_exp = list(primary_exp)
            existing_keys = {
                (e.get('company_name', '').lower(), e.get('title', '').lower(), e.get('start_date'))
                for e in primary_exp
            }
            
            for exp in secondary_exp:
                key = (exp.get('company_name', '').lower(), exp.get('title', '').lower(), exp.get('start_date'))
                if key not in existing_keys:
                    combined_exp.append(exp)
                    existing_keys.add(key)
                    merge_log.append(f"Experiencia agregada: {exp.get('title')} en {exp.get('company_name')}")
            
            # Sort by start date descending (handle None values safely)
            combined_exp.sort(key=lambda x: x.get('start_date') or '', reverse=True)
            merged_data['previous_companies'] = combined_exp
        
        # Merge education
        if merge_options.get('merge_education'):
            primary_edu = primary.get('education', []) or []
            secondary_edu = secondary.get('education', []) or []
            
            combined_edu = list(primary_edu)
            existing_edu = {
                (e.get('institution', '').lower(), e.get('degree', '').lower())
                for e in primary_edu
            }
            
            for edu in secondary_edu:
                key = (edu.get('institution', '').lower(), edu.get('degree', '').lower())
                if key not in existing_edu:
                    combined_edu.append(edu)
                    merge_log.append(f"Educación agregada: {edu.get('degree')} en {edu.get('institution')}")
            
            merged_data['education'] = combined_edu
        
        # Merge skills
        if merge_options.get('merge_skills'):
            primary_skills = set(primary.get('skills', []) or [])
            secondary_skills = set(secondary.get('skills', []) or [])
            new_skills = secondary_skills - primary_skills
            
            if new_skills:
                merged_data['skills'] = list(primary_skills | secondary_skills)
                merge_log.append(f"Skills agregados: {', '.join(new_skills)}")
        
        # Merge notes
        if merge_options.get('merge_notes'):
            primary_notes = primary.get('notes', '') or ''
            secondary_notes = secondary.get('notes', '') or ''
            
            if secondary_notes and secondary_notes not in primary_notes:
                separator = "\n\n---[Notas del registro fusionado]---\n\n"
                merged_data['notes'] = f"{primary_notes}{separator}{secondary_notes}"
                merge_log.append("Notas combinadas")
        
        # Handle CV versions
        if merge_options.get('keep_all_cvs'):
            # Store secondary CV as a version
            if secondary.get('resume_file_key'):
                cv_version = {
                    "id": str(uuid.uuid4()),
                    "candidate_id": primary_id,
                    "version": 0,  # Will be updated
                    "file_key": secondary.get('resume_file_key'),
                    "file_name": secondary.get('resume_file_name', 'cv_merged.pdf'),
                    "file_type": secondary.get('resume_file_type', 'application/pdf'),
                    "uploaded_at": secondary.get('created_at'),
                    "uploaded_by": secondary.get('created_by'),
                    "source": "merge",
                    "merged_from_candidate_id": secondary_id,
                    "is_current": False,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await self.db.cv_versions.insert_one(cv_version)
                merge_log.append("CV del registro secundario guardado como versión histórica")
        
        # Update primary candidate
        merged_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        merged_data['last_merge_at'] = datetime.now(timezone.utc).isoformat()
        
        await self.db.candidates.update_one(
            {"id": primary_id},
            {"$set": merged_data}
        )
        
        # Mark secondary as merged (soft delete with reference)
        await self.db.candidates.update_one(
            {"id": secondary_id},
            {"$set": {
                "is_deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deletion_type": "merged",
                "merged_into": primary_id,
                "merged_at": datetime.now(timezone.utc).isoformat(),
                "merged_by": merged_by
            }}
        )
        
        # Create audit log
        audit_record = {
            "id": str(uuid.uuid4()),
            "action": "candidate_merge",
            "primary_candidate_id": primary_id,
            "secondary_candidate_id": secondary_id,
            "primary_candidate_name": primary.get('full_name'),
            "secondary_candidate_name": secondary.get('full_name'),
            "merge_options": merge_options,
            "merge_log": merge_log,
            "merged_by": merged_by,
            "merged_at": datetime.now(timezone.utc).isoformat()
        }
        await self.db.merge_audit_log.insert_one(audit_record)
        
        # Update any assignments to point to primary
        await self.db.assignments.update_many(
            {"candidate_id": secondary_id},
            {"$set": {"candidate_id": primary_id, "migrated_from_merge": True}}
        )
        
        return {
            "success": True,
            "primary_id": primary_id,
            "secondary_id": secondary_id,
            "changes": merge_log,
            "audit_id": audit_record['id']
        }


# Initialize detector (will be done in server.py)
duplicate_detector_v2 = None
candidate_merger = None
