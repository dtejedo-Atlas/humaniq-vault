"""Classification-only chronology. Not imported by scoring or matching."""
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class EmploymentEvidence(BaseModel):
    company: str
    title: str = ''
    industry: Optional[str] = None
    company_size: Optional[str] = None
    company_basis: str = 'unknown'
    start: Optional[str] = None
    end: Optional[str] = None
    ongoing: bool = False
    evidence: str = Field(default='', max_length=600)


class ClassificationEvidence(BaseModel):
    model_config = ConfigDict(extra='ignore')
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None
    confidence_score: float = Field(ge=0, le=1)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    employments: list[EmploymentEvidence] = Field(default_factory=list, max_length=100)
    no_work_experience: bool = False
    reasoning: str = Field(default='', max_length=3000)
    uncertainty: list[str] = Field(default_factory=list, max_length=30)


def month_index(value):
    if not value or not re.fullmatch(r'\d{4}(?:-\d{2})?', value):
        return None
    year, month = int(value[:4]), int(value[5:7]) if len(value) == 7 else 1
    if not 1900 <= year <= 2200 or not 1 <= month <= 12:
        return None
    return year * 12 + month - 1


def employment_timeline(employments, today=None):
    today = today or datetime.now(timezone.utc)
    now = today.year * 12 + today.month - 1
    all_months, decade, uncertain = set(), defaultdict(set), []
    for job in employments:
        start = month_index(job.start)
        end = now if job.ongoing else month_index(job.end)
        if start is None or end is None or start > end or start > now:
            uncertain.append(job.company)
            continue
        end = min(end, now)
        months = set(range(start, end + 1))
        all_months.update(months)
        for month in months:
            if now - 119 <= month <= now:
                decade[month].add(job.industry)
    totals = defaultdict(float)
    for industries in decade.values():
        for industry in industries:
            totals[industry] += 1 / len(industries)
    known = sorted(((key, value) for key, value in totals.items() if key), key=lambda item: (-item[1], item[0]))
    dominant = known[0][0] if known else None
    ambiguous = not known or totals.get(None, 0) >= known[0][1] or (len(known) > 1 and abs(known[0][1] - known[1][1]) < .01)
    if ambiguous:
        dominant = None
    return {'industry': dominant, 'years_experience': len(all_months) // 12 if all_months else None,
            'experience_months': len(all_months), 'industry_months_last_decade': {str(k or 'unknown'): round(v, 2) for k, v in totals.items()},
            'undated_employers': uncertain, 'industry_ambiguous': ambiguous}