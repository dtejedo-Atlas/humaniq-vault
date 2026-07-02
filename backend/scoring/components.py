"""
Scoring Engine v3 - Components
10 funciones de componentes, cada una devuelve (xi: float 0-1, ci: float 0-1, evidence: dict|None).
Reutiliza funciones existentes vía import.
"""
import sys
import re
from typing import Tuple, Dict, Any, Optional, List
from datetime import datetime, date

# Añadir path para imports
sys.path.insert(0, '/app/backend')

# Imports de módulos existentes (REUTILIZACIÓN, no copia)
from affinity_matrices import get_functional_affinity, get_industry_transferability
from trajectory_analyzer import (
    calculate_trajectory_score,
    calculate_stability_score,
    get_seniority_index,
)
from embedding_service import EmbeddingService

# Import de config local
from .config_v3 import (
    SHRINKAGE_NEUTRAL,
    SEMANTIC_THRESHOLD,
    ER_CONFIG,
    ED_CONFIG,
    LO_CONFIG,
    CQ_CRITICAL_FIELDS,
)

# Tipo de retorno estándar para todos los componentes
ComponentResult = Tuple[float, float, Optional[Dict[str, Any]]]


# =============================================================================
# UTILIDADES INTERNAS
# =============================================================================

def _get_job_matching_service_utils():
    """
    Importa las utilidades de job_matching_service de forma lazy.
    Esto evita imports circulares y permite reutilizar el código existente.
    """
    from job_matching_service import JobMatchingService
    # Crear instancia temporal solo para acceder a métodos de utilidad
    return JobMatchingService(None, None)


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parsea una fecha desde string en varios formatos comunes."""
    if not date_str:
        return None
    
    # Si ya es date/datetime
    if isinstance(date_str, (date, datetime)):
        return date_str if isinstance(date_str, date) else date_str.date()
    
    date_str = str(date_str).strip()
    
    # Formatos comunes
    formats = [
        "%Y-%m-%d",
        "%Y-%m",
        "%Y",
        "%d/%m/%Y",
        "%m/%Y",
        "%B %Y",  # "January 2020"
        "%b %Y",  # "Jan 2020"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Intentar extraer solo el año
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if year_match:
        return date(int(year_match.group()), 1, 1)
    
    return None


def _calculate_tenure_years(start_date: Optional[str], end_date: Optional[str]) -> float:
    """
    Calcula años de tenure entre dos fechas.
    Si end_date es None/vacío, asume empleo actual (usa fecha actual).
    """
    start = _parse_date(start_date)
    if not start:
        return 0.0
    
    if end_date and str(end_date).strip().lower() not in ['', 'presente', 'actual', 'current', 'now']:
        end = _parse_date(end_date)
        if not end:
            end = date.today()
    else:
        end = date.today()
    
    delta = end - start
    return max(0.0, delta.days / 365.25)


def _infer_area_from_title(title: str) -> Optional[str]:
    """
    Infiere el área funcional a partir de un título de puesto.
    Mapeo simplificado basado en keywords comunes.
    """
    if not title:
        return None
    
    title_lower = title.lower()
    
    # Mapeo de keywords a áreas funcionales
    area_keywords = {
        "operations": ["operaciones", "operations", "supply chain", "cadena de suministro", "logística", "logistics", "producción", "production", "manufacturing", "planta"],
        "finance": ["finanzas", "finance", "financiero", "financial", "contabilidad", "accounting", "controller", "tesorería", "treasury", "fiscal", "tax"],
        "commercial": ["ventas", "sales", "comercial", "commercial", "business development", "desarrollo de negocio", "account", "cliente"],
        "marketing": ["marketing", "mercadotecnia", "brand", "marca", "comunicación", "communication", "digital", "growth"],
        "hr": ["recursos humanos", "human resources", "hr", "rrhh", "talento", "talent", "people", "capacitación", "training", "compensaciones"],
        "it_technology": ["tecnología", "technology", "ti", "it", "sistemas", "systems", "software", "developer", "desarrollo", "data", "analytics", "devops", "infrastructure"],
        "legal": ["legal", "jurídico", "abogado", "lawyer", "compliance", "cumplimiento", "regulatorio"],
        "general_management": ["director general", "ceo", "general manager", "gerente general", "country manager", "presidente", "president"],
        "supply_chain": ["supply chain", "cadena de suministro", "compras", "procurement", "purchasing", "sourcing"],
        "engineering": ["ingeniería", "engineering", "ingeniero", "engineer", "técnico", "technical", "mantenimiento", "maintenance"],
    }
    
    for area, keywords in area_keywords.items():
        for keyword in keywords:
            if keyword in title_lower:
                return area
    
    return None


def _is_executive_title(title: str) -> bool:
    """Verifica si un título es de nivel ejecutivo (director o superior)."""
    if not title:
        return False
    
    title_lower = title.lower()
    
    for exec_keyword in ED_CONFIG["executive_titles"]:
        if exec_keyword in title_lower:
            return True
    
    return False


# =============================================================================
# COMPONENTES (10 funciones)
# =============================================================================

def calculate_sk(
    candidate_skills: List[str],
    job_skills: List[str],
    job_has_skills: bool = True
) -> ComponentResult:
    """
    SK: Skills Coverage
    Cobertura de skills de la vacante vs candidate.skills.
    Reutiliza _normalize_skill, _skills_match y SKILL_SYNONYMS de job_matching_service.
    
    Args:
        candidate_skills: Lista de skills del candidato
        job_skills: Lista de skills requeridos por la vacante
        job_has_skills: Si la vacante tiene skills definidos
    
    Returns:
        (xi, ci, evidence)
    """
    # Si la vacante no tiene skills definidos
    if not job_has_skills or not job_skills:
        return (0.5, 0.0, {"note": "Vacante sin skills definidos"})
    
    if not candidate_skills:
        return (0.0, 1.0, {"matched": [], "missing": job_skills, "coverage": 0.0})
    
    # Obtener utilidades del job_matching_service
    jms = _get_job_matching_service_utils()
    
    matched = []
    for job_skill in job_skills:
        for cand_skill in candidate_skills:
            if jms._skills_match(cand_skill, job_skill):
                matched.append(job_skill)
                break
    
    coverage = len(matched) / len(job_skills)
    missing = [s for s in job_skills if s not in matched]
    
    return (
        min(1.0, coverage),
        1.0,
        {
            "matched": matched,
            "missing": missing,
            "coverage": round(coverage, 3),
            "matched_count": len(matched),
            "total_required": len(job_skills),
        }
    )


def calculate_er(
    candidate: Dict[str, Any],
    job: Dict[str, Any]
) -> ComponentResult:
    """
    ER: Experience Relevance
    Años de experiencia EN el área de la vacante.
    Itera previous_companies, calcula tenure, pondera por afinidad funcional.
    
    Args:
        candidate: Diccionario del candidato
        job: Diccionario de la vacante
    
    Returns:
        (xi, ci, evidence)
    """
    job_area = job.get("functional_area")
    min_experience = job.get("min_experience") or ER_CONFIG["default_min_years"]
    
    previous_companies = candidate.get("previous_companies", [])
    
    if not previous_companies:
        # Sin historial laboral
        years_exp = candidate.get("years_experience", 0)
        if years_exp and years_exp > 0:
            # Usar años totales con confianza baja
            xi = min(1.0, years_exp / max(min_experience, 1))
            return (xi, 0.3, {"note": "Sin previous_companies, usando years_experience global", "years": years_exp})
        return (0.0, 0.0, {"note": "Sin datos de experiencia"})
    
    total_relevant_years = 0.0
    jobs_with_dates = 0
    details = []
    
    for i, company in enumerate(previous_companies):
        title = company.get("title") or company.get("position", "")
        start_date = company.get("start_date")
        end_date = company.get("end_date")
        
        # Calcular tenure
        tenure = _calculate_tenure_years(start_date, end_date)
        has_dates = tenure > 0
        
        if has_dates:
            jobs_with_dates += 1
        
        # Inferir área del título
        inferred_area = _infer_area_from_title(title)
        
        # Calcular afinidad con el área de la vacante
        if job_area and inferred_area:
            affinity = get_functional_affinity(inferred_area, job_area) / 100.0
        elif not job_area:
            affinity = 1.0  # Si la vacante no tiene área, toda experiencia cuenta
        else:
            affinity = 0.5  # Si no se puede inferir área, afinidad neutral
        
        # Años relevantes = tenure * afinidad
        relevant_years = tenure * affinity
        
        # Boost si es empleo actual (último de la lista o sin end_date)
        is_current = (i == 0) or (not end_date or str(end_date).strip().lower() in ['', 'presente', 'actual', 'current'])
        if is_current:
            relevant_years *= ER_CONFIG["current_job_weight"]
        
        total_relevant_years += relevant_years
        
        details.append({
            "company": company.get("company_name", "N/A"),
            "title": title,
            "tenure_years": round(tenure, 2),
            "inferred_area": inferred_area,
            "affinity": round(affinity, 2),
            "relevant_years": round(relevant_years, 2),
            "is_current": is_current,
        })
    
    # Normalizar: xi = años_relevantes / min_experience, cap 1.0
    xi = min(1.0, total_relevant_years / max(min_experience, 1))
    
    # Confianza proporcional a empleos con fechas parseables
    ci = jobs_with_dates / len(previous_companies) if previous_companies else 0.0
    
    return (
        xi,
        ci,
        {
            "total_relevant_years": round(total_relevant_years, 2),
            "min_experience_required": min_experience,
            "jobs_analyzed": len(previous_companies),
            "jobs_with_dates": jobs_with_dates,
            "details": details,
        }
    )


def calculate_fa(
    candidate: Dict[str, Any],
    job: Dict[str, Any]
) -> ComponentResult:
    """
    FA: Functional Affinity
    Afinidad entre área funcional del candidato y de la vacante.
    
    Returns:
        (xi, ci, evidence)
    """
    cand_area = candidate.get("functional_area")
    job_area = job.get("functional_area")
    
    if not cand_area or not job_area:
        missing = []
        if not cand_area:
            missing.append("candidate.functional_area")
        if not job_area:
            missing.append("job.functional_area")
        return (SHRINKAGE_NEUTRAL, 0.0, {"note": "Datos faltantes", "missing": missing})
    
    affinity = get_functional_affinity(cand_area, job_area)
    xi = affinity / 100.0
    
    return (
        xi,
        1.0,
        {
            "candidate_area": cand_area,
            "job_area": job_area,
            "affinity_score": affinity,
        }
    )


def calculate_sa(
    candidate: Dict[str, Any],
    job: Dict[str, Any]
) -> ComponentResult:
    """
    SA: Seniority Alignment
    Alineación de seniority del candidato con la vacante.
    Reutiliza get_seniority_index de trajectory_analyzer.
    
    Returns:
        (xi, ci, evidence)
    """
    cand_seniority = candidate.get("seniority")
    job_seniority = job.get("seniority_level") or job.get("seniority")
    
    if not cand_seniority or not job_seniority:
        missing = []
        if not cand_seniority:
            missing.append("candidate.seniority")
        if not job_seniority:
            missing.append("job.seniority")
        return (SHRINKAGE_NEUTRAL, 0.0, {"note": "Datos faltantes", "missing": missing})
    
    # Obtener índices numéricos
    cand_index = get_seniority_index({"seniority": cand_seniority})
    
    # Para la vacante, construir dict temporal
    job_index = get_seniority_index({"seniority": job_seniority})
    
    # Calcular distancia (0 = match perfecto, mayor = más lejos)
    distance = abs(cand_index - job_index)
    max_distance = 9  # Máxima distancia posible (trainee a c_level)
    
    # Score: 1.0 para match exacto, decrece con distancia
    # Permitimos ±1 nivel con score alto
    if distance == 0:
        xi = 1.0
    elif distance == 1:
        xi = 0.85
    elif distance == 2:
        xi = 0.65
    else:
        xi = max(0.0, 1.0 - (distance / max_distance))
    
    return (
        xi,
        1.0,
        {
            "candidate_seniority": cand_seniority,
            "candidate_index": cand_index,
            "job_seniority": job_seniority,
            "job_index": job_index,
            "distance": distance,
        }
    )


def calculate_ia(
    candidate: Dict[str, Any],
    job: Dict[str, Any]
) -> ComponentResult:
    """
    IA: Industry Affinity
    Transferibilidad entre industria del candidato y de la vacante.
    
    Returns:
        (xi, ci, evidence)
    """
    cand_industry = candidate.get("industry")
    job_industry = job.get("industry")
    
    if not cand_industry or not job_industry:
        missing = []
        if not cand_industry:
            missing.append("candidate.industry")
        if not job_industry:
            missing.append("job.industry")
        return (SHRINKAGE_NEUTRAL, 0.0, {"note": "Datos faltantes", "missing": missing})
    
    transferability = get_industry_transferability(cand_industry, job_industry)
    xi = transferability / 100.0
    
    return (
        xi,
        1.0,
        {
            "candidate_industry": cand_industry,
            "job_industry": job_industry,
            "transferability_score": transferability,
        }
    )


def calculate_ed(
    candidate: Dict[str, Any]
) -> ComponentResult:
    """
    ED: Executive Depth
    Profundidad ejecutiva: combinación de seniority actual y historial de puestos ejecutivos.
    
    Formula: (índice_seniority/9)*0.6 + (proporción_empleos_ejecutivos)*0.4
    
    Returns:
        (xi, ci, evidence)
    """
    # Componente 1: Seniority actual
    seniority_index = get_seniority_index(candidate)
    seniority_component = seniority_index / ED_CONFIG["max_seniority_index"]
    
    # Componente 2: Historial ejecutivo
    previous_companies = candidate.get("previous_companies", [])
    
    if not previous_companies:
        # Sin historial, solo usar seniority
        xi = seniority_component * ED_CONFIG["seniority_weight"]
        return (
            xi,
            0.6,  # Confianza reducida sin historial
            {
                "seniority_index": seniority_index,
                "seniority_component": round(seniority_component, 3),
                "executive_ratio": 0.0,
                "note": "Sin previous_companies para evaluar historial ejecutivo",
            }
        )
    
    # Contar empleos con títulos ejecutivos
    executive_count = 0
    titles_analyzed = []
    
    for company in previous_companies:
        title = company.get("title") or company.get("position", "")
        is_exec = _is_executive_title(title)
        if is_exec:
            executive_count += 1
        titles_analyzed.append({"title": title, "is_executive": is_exec})
    
    executive_ratio = executive_count / len(previous_companies)
    
    # Combinar componentes
    xi = (
        seniority_component * ED_CONFIG["seniority_weight"] +
        executive_ratio * ED_CONFIG["history_weight"]
    )
    
    return (
        min(1.0, xi),
        1.0,
        {
            "seniority_index": seniority_index,
            "seniority_component": round(seniority_component, 3),
            "executive_count": executive_count,
            "total_positions": len(previous_companies),
            "executive_ratio": round(executive_ratio, 3),
            "titles_analyzed": titles_analyzed[:5],  # Limitar para no llenar evidence
        }
    )


def calculate_tr(
    candidate: Dict[str, Any]
) -> ComponentResult:
    """
    TR: Trajectory Score
    Score de trayectoria profesional.
    Reutiliza calculate_trajectory_score de trajectory_analyzer.
    
    Returns:
        (xi, ci, evidence)
    """
    try:
        trajectory_score = calculate_trajectory_score(candidate)
        xi = trajectory_score / 100.0
        
        # También obtener estabilidad para evidencia adicional
        stability_score, stability_warning, stability_detail = calculate_stability_score(candidate)
        
        return (
            xi,
            1.0,
            {
                "trajectory_score_raw": trajectory_score,
                "stability_score": stability_score,
                "stability_warning": stability_warning,
                "stability_detail": stability_detail,
            }
        )
    except Exception as e:
        return (
            SHRINKAGE_NEUTRAL,
            0.0,
            {"error": str(e), "note": "Error calculando trajectory"}
        )


def calculate_lo(
    candidate: Dict[str, Any],
    job: Dict[str, Any]
) -> ComponentResult:
    """
    LO: Location Fit
    Ajuste de ubicación considerando work_scheme.
    SIN componente salarial (salary_data no está poblado).
    
    Returns:
        (xi, ci, evidence)
    """
    work_scheme = job.get("work_scheme", "").lower()
    
    # Si es remoto, score automático 1.0
    if work_scheme in ["remoto", "remote", "full_remote", "100% remoto"]:
        return (
            LO_CONFIG["remote_score"],
            1.0,
            {"work_scheme": work_scheme, "note": "Remoto = ubicación no relevante"}
        )
    
    cand_city = (candidate.get("city") or "").strip().lower()
    cand_state = (candidate.get("state") or "").strip().lower()
    job_city = (job.get("city") or "").strip().lower()
    job_state = (job.get("state") or "").strip().lower()
    
    # Si faltan datos del candidato
    if not cand_city and not cand_state:
        return (
            LO_CONFIG["missing_data_score"],
            LO_CONFIG["missing_data_confidence"],
            {"note": "Candidato sin datos de ubicación (city/state)"}
        )
    
    # Si faltan datos de la vacante
    if not job_city and not job_state:
        return (
            LO_CONFIG["missing_data_score"],
            LO_CONFIG["missing_data_confidence"],
            {"note": "Vacante sin datos de ubicación (city/state)"}
        )
    
    # Comparar ubicación
    if cand_city and job_city and cand_city == job_city:
        xi = LO_CONFIG["same_city_score"]
        match_level = "same_city"
    elif cand_state and job_state and cand_state == job_state:
        xi = LO_CONFIG["same_state_score"]
        match_level = "same_state"
    else:
        xi = LO_CONFIG["different_location"]
        match_level = "different"
    
    return (
        xi,
        1.0,
        {
            "candidate_city": cand_city or None,
            "candidate_state": cand_state or None,
            "job_city": job_city or None,
            "job_state": job_state or None,
            "work_scheme": work_scheme or "presencial",
            "match_level": match_level,
        }
    )


def calculate_sm(
    candidate_embedding: Optional[List[float]],
    job_embedding: Optional[List[float]]
) -> ComponentResult:
    """
    SM: Semantic Similarity
    Similitud semántica entre embeddings.
    Remapeado de [SEMANTIC_THRESHOLD, 1] a [0, 1].
    
    Returns:
        (xi, ci, evidence)
    """
    if not candidate_embedding or not job_embedding:
        missing = []
        if not candidate_embedding:
            missing.append("candidate.embedding")
        if not job_embedding:
            missing.append("job.embedding")
        return (
            SHRINKAGE_NEUTRAL,
            0.0,
            {"note": "Embedding faltante", "missing": missing}
        )
    
    # Calcular similitud coseno
    raw_similarity = EmbeddingService.calculate_similarity(candidate_embedding, job_embedding)
    
    # Remapear de [SEMANTIC_THRESHOLD, 1] a [0, 1]
    if raw_similarity < SEMANTIC_THRESHOLD:
        xi = 0.0
    else:
        xi = (raw_similarity - SEMANTIC_THRESHOLD) / (1.0 - SEMANTIC_THRESHOLD)
    
    return (
        min(1.0, xi),
        1.0,
        {
            "raw_similarity": round(raw_similarity, 4),
            "remapped_score": round(xi, 4),
            "threshold_used": SEMANTIC_THRESHOLD,
        }
    )


def calculate_cq(
    candidate: Dict[str, Any]
) -> ComponentResult:
    """
    CQ: CV Quality / Completeness
    Completitud de campos críticos del CV.
    
    Campos evaluados:
    - email
    - phone
    - current_title
    - skills (≥3)
    - previous_companies (≥1)
    - previous_companies con fechas
    - languages (≥1)
    - years_experience
    
    Returns:
        (xi, ci, evidence)
    """
    checks = {}
    present = 0
    total = 8
    
    # 1. email
    has_email = bool(candidate.get("email") and str(candidate.get("email")).strip())
    checks["email"] = has_email
    if has_email:
        present += 1
    
    # 2. phone
    has_phone = bool(candidate.get("phone") and str(candidate.get("phone")).strip())
    checks["phone"] = has_phone
    if has_phone:
        present += 1
    
    # 3. current_title
    has_title = bool(candidate.get("current_title") and str(candidate.get("current_title")).strip())
    checks["current_title"] = has_title
    if has_title:
        present += 1
    
    # 4. skills >= 3
    skills = candidate.get("skills", [])
    has_skills = isinstance(skills, list) and len(skills) >= 3
    checks["skills_min_3"] = has_skills
    if has_skills:
        present += 1
    
    # 5. previous_companies >= 1
    pcs = candidate.get("previous_companies", [])
    has_pcs = isinstance(pcs, list) and len(pcs) >= 1
    checks["previous_companies_min_1"] = has_pcs
    if has_pcs:
        present += 1
    
    # 6. previous_companies con fechas
    has_dates = False
    if has_pcs:
        has_dates = any(
            pc.get("start_date") or pc.get("end_date")
            for pc in pcs
        )
    checks["previous_companies_dates"] = has_dates
    if has_dates:
        present += 1
    
    # 7. languages >= 1
    languages = candidate.get("languages", [])
    has_languages = isinstance(languages, list) and len(languages) >= 1
    checks["languages_min_1"] = has_languages
    if has_languages:
        present += 1
    
    # 8. years_experience
    years_exp = candidate.get("years_experience")
    has_years = years_exp is not None and years_exp > 0
    checks["years_experience"] = has_years
    if has_years:
        present += 1
    
    xi = present / total
    
    return (
        xi,
        1.0,  # Confianza siempre 1 para este componente
        {
            "present": present,
            "total": total,
            "checks": checks,
        }
    )
