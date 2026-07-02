"""
Scoring Engine v3 - Confidence / HEC (Hierarchical Evidence Confidence)
Calcula el nivel de confianza general basado en 6 señales de evidencia.

HEC = 0.25*EC + 0.20*PC + 0.20*HV + 0.15*DC + 0.10*CV + 0.10*RC

donde:
- EC = proporción de los 10 componentes con ci > 0.5
- PC = ai_classification.confidence_score (default 0.5 si no existe)
- HV = 1.0 si ai_classification.approved_by_recruiter o was_corrected; si no 0.5
- DC = promedio de 4 checks: email presente, previous_companies con fechas, skills no vacío, functional_area presente
- CV = el xi del componente CQ (pasado desde components)
- RC = recencia del último resume_file.upload_date: <180 días=1.0, <365=0.8, <730=0.6, más o sin archivo=0.4
"""
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone


# =============================================================================
# PESOS HEC (Hierarchical Evidence Confidence)
# =============================================================================
HEC_WEIGHTS = {
    "EC": 0.25,  # Experience Confidence - proporción de componentes con ci > 0.5
    "PC": 0.20,  # Parsing Confidence - ai_classification.confidence_score
    "HV": 0.20,  # Human Validation - validación humana (aprobación/corrección)
    "DC": 0.15,  # Data Completeness - completitud de 4 campos críticos
    "CV": 0.10,  # CV Quality - xi del componente CQ
    "RC": 0.10,  # Resume Currency - recencia del upload_date
}

# Validar que sumen 1.0
_hec_sum = sum(HEC_WEIGHTS.values())
assert abs(_hec_sum - 1.0) < 1e-9, f"HEC_WEIGHTS must sum to 1.0, got {_hec_sum}"


# =============================================================================
# SEÑALES DE CONFIANZA
# =============================================================================

def calculate_ec(components: Dict[str, Dict[str, Any]]) -> Tuple[float, Dict]:
    """
    EC: Experience Confidence
    Proporción de los 10 componentes con ci > 0.5
    
    Args:
        components: Diccionario de componentes con sus scores
    
    Returns:
        (score 0-1, evidence dict)
    """
    if not components:
        return (0.0, {"note": "Sin componentes", "components_high_ci": 0, "total": 0})
    
    high_confidence_count = 0
    component_details = []
    
    for code, comp_data in components.items():
        ci = comp_data.get("confidence", 0.0)
        is_high = ci > 0.5
        if is_high:
            high_confidence_count += 1
        component_details.append({
            "code": code,
            "ci": round(ci, 3),
            "high_confidence": is_high
        })
    
    total = len(components)
    score = high_confidence_count / total if total > 0 else 0.0
    
    return (
        score,
        {
            "components_high_ci": high_confidence_count,
            "total": total,
            "details": component_details,
        }
    )


def calculate_pc(candidate: Dict[str, Any]) -> Tuple[float, Dict]:
    """
    PC: Parsing Confidence
    ai_classification.confidence_score (default 0.5 si no existe)
    
    Returns:
        (score 0-1, evidence dict)
    """
    ai_class = candidate.get("ai_classification", {})
    
    if not ai_class:
        return (0.5, {"note": "Sin ai_classification", "source": "default"})
    
    confidence_score = ai_class.get("confidence_score")
    
    if confidence_score is not None:
        return (
            float(confidence_score),
            {
                "source": "ai_classification.confidence_score",
                "raw_score": confidence_score,
            }
        )
    
    # Default si no hay confidence_score
    return (0.5, {"note": "ai_classification sin confidence_score", "source": "default"})


def calculate_hv(candidate: Dict[str, Any]) -> Tuple[float, Dict]:
    """
    HV: Human Validation
    1.0 si ai_classification.approved_by_recruiter o was_corrected; si no 0.5
    
    Returns:
        (score 0-1, evidence dict)
    """
    ai_class = candidate.get("ai_classification", {})
    
    if not ai_class:
        return (0.5, {"note": "Sin ai_classification", "approved": False, "corrected": False})
    
    approved = ai_class.get("approved_by_recruiter", False)
    corrected = ai_class.get("was_corrected", False)
    
    if approved or corrected:
        return (
            1.0,
            {
                "approved": approved,
                "corrected": corrected,
                "note": "Validado por humano"
            }
        )
    else:
        return (
            0.5,
            {
                "approved": False,
                "corrected": False,
                "note": "Sin validación humana"
            }
        )


def calculate_dc(candidate: Dict[str, Any]) -> Tuple[float, Dict]:
    """
    DC: Data Completeness
    Promedio de 4 checks:
    - email presente
    - previous_companies con fechas
    - skills no vacío
    - functional_area presente
    
    Returns:
        (score 0-1, evidence dict)
    """
    checks = {}
    passed = 0
    
    # 1. email presente
    has_email = bool(candidate.get("email") and str(candidate.get("email")).strip())
    checks["email_present"] = has_email
    if has_email:
        passed += 1
    
    # 2. previous_companies con fechas
    pcs = candidate.get("previous_companies", [])
    has_dates = False
    if pcs and isinstance(pcs, list):
        for pc in pcs:
            if pc.get("start_date") or pc.get("end_date"):
                has_dates = True
                break
    checks["previous_companies_with_dates"] = has_dates
    if has_dates:
        passed += 1
    
    # 3. skills no vacío
    skills = candidate.get("skills", [])
    has_skills = bool(skills and isinstance(skills, list) and len(skills) > 0)
    checks["skills_not_empty"] = has_skills
    if has_skills:
        passed += 1
    
    # 4. functional_area presente
    has_fa = bool(candidate.get("functional_area") and str(candidate.get("functional_area")).strip())
    checks["functional_area_present"] = has_fa
    if has_fa:
        passed += 1
    
    score = passed / 4.0
    
    return (
        score,
        {
            "passed": passed,
            "total": 4,
            "checks": checks,
        }
    )


def calculate_cv_signal(cq_xi: float) -> Tuple[float, Dict]:
    """
    CV: CV Quality Signal
    El xi del componente CQ (pasado desde components)
    
    Args:
        cq_xi: El raw score del componente CQ
    
    Returns:
        (score 0-1, evidence dict)
    """
    return (
        cq_xi,
        {
            "source": "component_CQ.xi",
            "cq_score": round(cq_xi, 4),
        }
    )


def calculate_rc(candidate: Dict[str, Any]) -> Tuple[float, Dict]:
    """
    RC: Resume Currency
    Recencia del último resume_file.upload_date:
    - <180 días = 1.0
    - <365 días = 0.8
    - <730 días = 0.6
    - más o sin archivo = 0.4
    
    Returns:
        (score 0-1, evidence dict)
    """
    resume_files = candidate.get("resume_files", [])
    
    if not resume_files:
        return (0.4, {"note": "Sin archivos de CV", "days_old": None})
    
    # Buscar la fecha más reciente
    latest_date = None
    
    for rf in resume_files:
        upload_date = rf.get("upload_date")
        if upload_date:
            try:
                if isinstance(upload_date, str):
                    if "T" in upload_date:
                        parsed = datetime.fromisoformat(upload_date.replace("Z", "+00:00"))
                    else:
                        parsed = datetime.strptime(upload_date[:10], "%Y-%m-%d")
                        parsed = parsed.replace(tzinfo=timezone.utc)
                elif isinstance(upload_date, datetime):
                    parsed = upload_date
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                else:
                    continue
                
                if latest_date is None or parsed > latest_date:
                    latest_date = parsed
            except (ValueError, TypeError):
                continue
    
    if latest_date is None:
        return (0.4, {"note": "Sin fecha de upload parseable", "days_old": None})
    
    now = datetime.now(timezone.utc)
    days_old = (now - latest_date).days
    
    if days_old < 180:
        score = 1.0
    elif days_old < 365:
        score = 0.8
    elif days_old < 730:
        score = 0.6
    else:
        score = 0.4
    
    return (
        score,
        {
            "latest_upload_date": str(latest_date)[:10],
            "days_old": days_old,
        }
    )


# =============================================================================
# FUNCIÓN PRINCIPAL: calculate_hec
# =============================================================================

def calculate_hec(
    candidate: Dict[str, Any],
    components: Dict[str, Dict[str, Any]]
) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula el HEC (Hierarchical Evidence Confidence) del candidato.
    
    HEC = 0.25*EC + 0.20*PC + 0.20*HV + 0.15*DC + 0.10*CV + 0.10*RC
    
    Args:
        candidate: Diccionario del candidato
        components: Diccionario de componentes ya calculados (con raw, confidence, etc.)
    
    Returns:
        (hec_score: float 0-1, breakdown: dict con cada señal)
    """
    # Extraer CQ.xi para la señal CV
    cq_component = components.get("CQ", {})
    cq_xi = cq_component.get("raw", 0.5)
    
    # Calcular cada señal
    ec_score, ec_evidence = calculate_ec(components)
    pc_score, pc_evidence = calculate_pc(candidate)
    hv_score, hv_evidence = calculate_hv(candidate)
    dc_score, dc_evidence = calculate_dc(candidate)
    cv_score, cv_evidence = calculate_cv_signal(cq_xi)
    rc_score, rc_evidence = calculate_rc(candidate)
    
    # Calcular HEC ponderado
    hec = (
        HEC_WEIGHTS["EC"] * ec_score +
        HEC_WEIGHTS["PC"] * pc_score +
        HEC_WEIGHTS["HV"] * hv_score +
        HEC_WEIGHTS["DC"] * dc_score +
        HEC_WEIGHTS["CV"] * cv_score +
        HEC_WEIGHTS["RC"] * rc_score
    )
    
    # Clamp a [0, 1]
    hec = max(0.0, min(1.0, hec))
    
    breakdown = {
        "EC": {
            "weight": HEC_WEIGHTS["EC"],
            "score": round(ec_score, 4),
            "weighted": round(HEC_WEIGHTS["EC"] * ec_score, 4),
            "description": "Proporción componentes con ci > 0.5",
            "evidence": ec_evidence,
        },
        "PC": {
            "weight": HEC_WEIGHTS["PC"],
            "score": round(pc_score, 4),
            "weighted": round(HEC_WEIGHTS["PC"] * pc_score, 4),
            "description": "ai_classification.confidence_score",
            "evidence": pc_evidence,
        },
        "HV": {
            "weight": HEC_WEIGHTS["HV"],
            "score": round(hv_score, 4),
            "weighted": round(HEC_WEIGHTS["HV"] * hv_score, 4),
            "description": "Validación humana (aprobado/corregido)",
            "evidence": hv_evidence,
        },
        "DC": {
            "weight": HEC_WEIGHTS["DC"],
            "score": round(dc_score, 4),
            "weighted": round(HEC_WEIGHTS["DC"] * dc_score, 4),
            "description": "Completitud de 4 campos críticos",
            "evidence": dc_evidence,
        },
        "CV": {
            "weight": HEC_WEIGHTS["CV"],
            "score": round(cv_score, 4),
            "weighted": round(HEC_WEIGHTS["CV"] * cv_score, 4),
            "description": "CV Quality (CQ.xi)",
            "evidence": cv_evidence,
        },
        "RC": {
            "weight": HEC_WEIGHTS["RC"],
            "score": round(rc_score, 4),
            "weighted": round(HEC_WEIGHTS["RC"] * rc_score, 4),
            "description": "Recencia del CV upload",
            "evidence": rc_evidence,
        },
    }
    
    return (round(hec, 4), breakdown)
