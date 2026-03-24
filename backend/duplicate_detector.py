from typing import List, Dict, Optional
import re
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)

class DuplicateDetector:
    def __init__(self, db):
        self.db = db
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number for comparison"""
        if not phone:
            return ""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        # Remove country code if present (assuming Mexico +52)
        if digits.startswith('52') and len(digits) > 10:
            digits = digits[2:]
        return digits
    
    @staticmethod
    def normalize_linkedin(url: str) -> str:
        """Normalize LinkedIn URL for comparison"""
        if not url:
            return ""
        # Extract username from various LinkedIn URL formats
        patterns = [
            r'linkedin\.com/in/([^/?]+)',
            r'linkedin\.com/pub/([^/?]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url.lower())
            if match:
                return match.group(1).strip('/')
        return url.lower().strip('/')
    
    @staticmethod
    def name_similarity(name1: str, name2: str) -> float:
        """Calculate similarity between two names (0.0 to 1.0)"""
        if not name1 or not name2:
            return 0.0
        
        # Normalize: lowercase, remove extra spaces
        n1 = ' '.join(name1.lower().split())
        n2 = ' '.join(name2.lower().split())
        
        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, n1, n2).ratio()
    
    @staticmethod
    def get_common_companies(companies1: List[Dict], companies2: List[Dict]) -> List[str]:
        """Find common companies between two candidate histories"""
        if not companies1 or not companies2:
            return []
        
        names1 = {c.get('company_name', '').lower() for c in companies1 if c.get('company_name')}
        names2 = {c.get('company_name', '').lower() for c in companies2 if c.get('company_name')}
        
        common = names1.intersection(names2)
        return list(common)
    
    async def detect_duplicates(self, candidate_data: dict) -> List[Dict]:
        """Detect potential duplicate candidates"""
        matches = []
        
        # NIVEL 1: Email (100% confidence)
        if email := candidate_data.get('email'):
            existing = await self.db.candidates.find_one(
                {"email": email},
                {"_id": 0, "id": 1, "full_name": 1, "current_title": 1, "current_company": 1, "email": 1}
            )
            if existing:
                matches.append({
                    "candidate_id": existing['id'],
                    "candidate_name": existing.get('full_name'),
                    "candidate_title": existing.get('current_title'),
                    "candidate_company": existing.get('current_company'),
                    "match_type": "email",
                    "confidence": 1.0,
                    "reason": "Email idéntico"
                })
                return matches  # Email match is conclusive
        
        # NIVEL 2: LinkedIn (95% confidence)
        if linkedin := candidate_data.get('linkedin_url'):
            normalized = self.normalize_linkedin(linkedin)
            if normalized:
                # Find candidates with similar LinkedIn URLs
                all_candidates = await self.db.candidates.find(
                    {"linkedin_url": {"$ne": None}},
                    {"_id": 0, "id": 1, "full_name": 1, "linkedin_url": 1, "current_title": 1, "current_company": 1}
                ).to_list(1000)
                
                for candidate in all_candidates:
                    if self.normalize_linkedin(candidate.get('linkedin_url', '')) == normalized:
                        matches.append({
                            "candidate_id": candidate['id'],
                            "candidate_name": candidate.get('full_name'),
                            "candidate_title": candidate.get('current_title'),
                            "candidate_company": candidate.get('current_company'),
                            "match_type": "linkedin",
                            "confidence": 0.95,
                            "reason": "Perfil de LinkedIn idéntico"
                        })
                        return matches  # LinkedIn match is highly conclusive
        
        # NIVEL 3: Teléfono (90% confidence)
        if phone := candidate_data.get('phone'):
            normalized = self.normalize_phone(phone)
            if normalized and len(normalized) >= 10:
                # Search for similar phone numbers
                all_candidates = await self.db.candidates.find(
                    {"phone": {"$ne": None}},
                    {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "current_title": 1, "current_company": 1}
                ).to_list(1000)
                
                for candidate in all_candidates:
                    if self.normalize_phone(candidate.get('phone', '')) == normalized:
                        matches.append({
                            "candidate_id": candidate['id'],
                            "candidate_name": candidate.get('full_name'),
                            "candidate_title": candidate.get('current_title'),
                            "candidate_company": candidate.get('current_company'),
                            "match_type": "phone",
                            "confidence": 0.90,
                            "reason": "Teléfono idéntico"
                        })
        
        # NIVEL 4: Nombre similar (70-85% confidence)
        if full_name := candidate_data.get('full_name'):
            all_candidates = await self.db.candidates.find(
                {},
                {"_id": 0, "id": 1, "full_name": 1, "previous_companies": 1, "current_title": 1, "current_company": 1}
            ).to_list(500)
            
            for candidate in all_candidates:
                name_sim = self.name_similarity(full_name, candidate.get('full_name', ''))
                
                if name_sim >= 0.85:  # High name similarity
                    # Check for common companies
                    common_companies = self.get_common_companies(
                        candidate_data.get('previous_companies', []),
                        candidate.get('previous_companies', [])
                    )
                    
                    if common_companies:
                        confidence = 0.85
                        reason = f"Nombre muy similar ({int(name_sim*100)}%) + trabajó en {', '.join(common_companies)}"
                    else:
                        confidence = 0.70
                        reason = f"Nombre muy similar ({int(name_sim*100)}%)"
                    
                    matches.append({
                        "candidate_id": candidate['id'],
                        "candidate_name": candidate.get('full_name'),
                        "candidate_title": candidate.get('current_title'),
                        "candidate_company": candidate.get('current_company'),
                        "match_type": "name_similarity",
                        "confidence": confidence,
                        "reason": reason
                    })
        
        # Sort by confidence and return top matches
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches[:5]  # Return top 5 matches

class DuplicateSuggestion:
    """Store duplicate suggestions for manual review"""
    
    @staticmethod
    async def create_suggestion(db, new_candidate_id: str, duplicate_matches: List[Dict], created_by: str):
        """Create duplicate suggestions in database"""
        if not duplicate_matches:
            return
        
        from datetime import datetime, timezone
        import uuid
        
        suggestions = []
        for match in duplicate_matches:
            suggestion = {
                "id": str(uuid.uuid4()),
                "new_candidate_id": new_candidate_id,
                "potential_duplicate_id": match['candidate_id'],
                "match_type": match['match_type'],
                "confidence": match['confidence'],
                "reason": match['reason'],
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
                "created_by": created_by,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            suggestions.append(suggestion)
        
        if suggestions:
            await db.duplicate_suggestions.insert_many(suggestions)