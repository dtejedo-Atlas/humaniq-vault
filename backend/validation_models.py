from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, timezone

class ValidationRecord(BaseModel):
    """Record for tracking AI classification quality"""
    model_config = ConfigDict(extra="ignore")
    id: str
    candidate_id: str
    candidate_name: str
    
    # Expected classifications (ground truth)
    expected_industry: Optional[str] = None
    expected_functional_area: Optional[str] = None
    expected_seniority: Optional[str] = None
    
    # Atlas classifications
    atlas_industry: Optional[str] = None
    atlas_functional_area: Optional[str] = None
    atlas_seniority: Optional[str] = None
    
    # Evaluation
    industry_correct: Optional[bool] = None
    functional_area_correct: Optional[bool] = None
    seniority_correct: Optional[bool] = None
    
    # Parsing quality
    parsing_quality_score: Optional[int] = None  # 1-5
    parsing_notes: Optional[str] = None
    
    # Search relevance (for specific queries)
    search_query: Optional[str] = None
    search_relevant: Optional[bool] = None
    search_notes: Optional[str] = None
    
    # Overall
    reviewer_name: str
    comments: Optional[str] = None
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
class ValidationSummary(BaseModel):
    """Summary statistics for validation"""
    total_evaluated: int
    industry_accuracy: float
    functional_area_accuracy: float
    seniority_accuracy: float
    avg_parsing_quality: float
    search_relevance_rate: float
    common_errors: List[dict]
