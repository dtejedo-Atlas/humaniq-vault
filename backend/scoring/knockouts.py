"""
Scoring Engine v3 - Knockouts
Evaluadores de knockout que determinan si un candidato cumple requisitos mínimos.
"""
import re
from typing import Tuple, List, Dict, Any, Optional

from .config_v3 import KNOCKOUT_VALUES


# Tipo de retorno para evaluadores individuales
KnockoutResult = Dict[str, Any]  # {"status": str, "value": float, "note": str, ...}

# Tipo de retorno para evaluate_knockouts
KnockoutEvaluation = Tuple[float, List[KnockoutResult]]


# =============================================================================
# UTILIDADES INTERNAS
# =============================================================================

def _normalize_language(lang: str) -> str:
    """Normaliza un idioma para comparación flexible."""
    if not lang:
        return ""
    
    lang = lang.lower().strip()
    
    # Remover niveles entre paréntesis: "Inglés (Avanzado)" -> "inglés"
    lang = re.sub(r'\s*\([^)]*\)\s*', '', lang)
    
    # Mapeo de variantes comunes
    variants = {
        "english": "english",
        "inglés": "english",
        "ingles": "english",
        "spanish": "spanish",
        "español": "spanish",
        "espanol": "spanish",
        "portuguese": "portuguese",
        "portugués": "portuguese",
        "portugues": "portuguese",
        "french": "french",
        "francés": "french",
        "frances": "french",
        "german": "german",
        "alemán": "german",
        "aleman": "german",
        "italian": "italian",
        "italiano": "italian",
        "chinese": "chinese",
        "chino": "chinese",
        "mandarin": "chinese",
        "mandarín": "chinese",
        "japanese": "japanese",
        "japonés": "japanese",
        "japones": "japanese",
    }
    
    return variants.get(lang, lang)


def _languages_match(candidate_lang: str, required_lang: str) -> bool:
    """Verifica si un idioma del candidato cumple con el requerido."""
    norm_cand = _normalize_language(candidate_lang)
    norm_req = _normalize_language(required_lang)
    
    if not norm_cand or not norm_req:
        return False
    
    # Match exacto o parcial
    return norm_cand == norm_req or norm_req in norm_cand or norm_cand in norm_req


# =============================================================================
# EVALUADORES INDIVIDUALES
# =============================================================================

def evaluate_language_knockout(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None
) -> KnockoutResult:
    """
    Evalúa si el candidato cumple con los idiomas requeridos.
    
    Args:
        candidate: Diccionario del candidato
        job: Diccionario de la vacante
        scorecard: Scorecard opcional (futuro, Fase 4)
    
    Returns:
        KnockoutResult con status, value y detalles
    """
    # Obtener idiomas requeridos de la vacante
    required_languages = job.get("required_languages", [])
    
    # Si la vacante no especifica idiomas, no es knockout
    if not required_languages:
        return {
            "evaluator": "language",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": "Vacante sin requisito de idiomas",
            "required": [],
            "candidate_languages": candidate.get("languages", []),
        }
    
    candidate_languages = candidate.get("languages", [])
    
    # Si el candidato no tiene idiomas registrados
    if not candidate_languages:
        return {
            "evaluator": "language",
            "status": "evidencia_insuficiente",
            "value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": "Candidato sin idiomas registrados",
            "required": required_languages,
            "candidate_languages": [],
        }
    
    # Verificar cada idioma requerido
    matched = []
    missing = []
    
    for req_lang in required_languages:
        found = False
        for cand_lang in candidate_languages:
            if _languages_match(cand_lang, req_lang):
                matched.append(req_lang)
                found = True
                break
        if not found:
            missing.append(req_lang)
    
    # Determinar resultado
    if not missing:
        return {
            "evaluator": "language",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": "Todos los idiomas requeridos presentes",
            "required": required_languages,
            "matched": matched,
            "missing": [],
            "candidate_languages": candidate_languages,
        }
    elif len(matched) > 0:
        return {
            "evaluator": "language",
            "status": "parcial",
            "value": KNOCKOUT_VALUES["parcial"],
            "note": f"Faltan idiomas: {', '.join(missing)}",
            "required": required_languages,
            "matched": matched,
            "missing": missing,
            "candidate_languages": candidate_languages,
        }
    else:
        return {
            "evaluator": "language",
            "status": "no_cumple_importante",
            "value": KNOCKOUT_VALUES["no_cumple_importante"],
            "note": f"No tiene ningún idioma requerido: {', '.join(missing)}",
            "required": required_languages,
            "matched": [],
            "missing": missing,
            "candidate_languages": candidate_languages,
        }


def evaluate_location_knockout(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None
) -> KnockoutResult:
    """
    Evalúa si el candidato cumple con la ubicación requerida.
    Considera work_scheme (remoto no requiere ubicación).
    
    Returns:
        KnockoutResult
    """
    work_scheme = job.get("work_scheme", "").lower()
    
    # Si es remoto, siempre cumple
    if work_scheme in ["remoto", "remote", "full_remote", "100% remoto"]:
        return {
            "evaluator": "location",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": "Posición remota - ubicación no es requisito",
            "work_scheme": work_scheme,
        }
    
    # Si es híbrido, ubicación es importante pero no fatal
    is_hybrid = work_scheme in ["híbrido", "hybrid", "hibrido"]
    
    job_city = (job.get("city") or "").strip().lower()
    job_state = (job.get("state") or "").strip().lower()
    
    # Si la vacante no especifica ubicación
    if not job_city and not job_state:
        return {
            "evaluator": "location",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": "Vacante sin requisito de ubicación específica",
            "work_scheme": work_scheme or "presencial",
        }
    
    cand_city = (candidate.get("city") or "").strip().lower()
    cand_state = (candidate.get("state") or "").strip().lower()
    
    # Si el candidato no tiene ubicación registrada
    if not cand_city and not cand_state:
        return {
            "evaluator": "location",
            "status": "evidencia_insuficiente",
            "value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": "Candidato sin ubicación registrada",
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }
    
    # Comparar ubicaciones
    same_city = job_city and cand_city and job_city == cand_city
    same_state = job_state and cand_state and job_state == cand_state
    
    if same_city:
        return {
            "evaluator": "location",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": "Misma ciudad",
            "candidate_location": {"city": cand_city, "state": cand_state},
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }
    elif same_state:
        status = "cumple" if is_hybrid else "parcial"
        return {
            "evaluator": "location",
            "status": status,
            "value": KNOCKOUT_VALUES[status],
            "note": "Mismo estado, diferente ciudad",
            "candidate_location": {"city": cand_city, "state": cand_state},
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }
    else:
        # Diferente ubicación
        status = "parcial" if is_hybrid else "no_cumple_importante"
        return {
            "evaluator": "location",
            "status": status,
            "value": KNOCKOUT_VALUES[status],
            "note": "Ubicación diferente",
            "candidate_location": {"city": cand_city, "state": cand_state},
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }


def evaluate_experience_knockout(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None
) -> KnockoutResult:
    """
    Evalúa si el candidato cumple con la experiencia mínima requerida.
    
    Returns:
        KnockoutResult
    """
    min_experience = job.get("min_experience")
    
    # Si la vacante no especifica experiencia mínima
    if not min_experience or min_experience <= 0:
        return {
            "evaluator": "experience",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": "Vacante sin requisito de experiencia mínima",
        }
    
    candidate_years = candidate.get("years_experience")
    
    # Si el candidato no tiene años de experiencia registrados
    if candidate_years is None:
        return {
            "evaluator": "experience",
            "status": "evidencia_insuficiente",
            "value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": "Candidato sin años de experiencia registrados",
            "required_years": min_experience,
        }
    
    # Comparar experiencia
    if candidate_years >= min_experience:
        return {
            "evaluator": "experience",
            "status": "cumple",
            "value": KNOCKOUT_VALUES["cumple"],
            "note": f"Experiencia suficiente: {candidate_years} >= {min_experience} años",
            "candidate_years": candidate_years,
            "required_years": min_experience,
        }
    elif candidate_years >= min_experience * 0.8:  # Dentro del 80%
        return {
            "evaluator": "experience",
            "status": "parcial",
            "value": KNOCKOUT_VALUES["parcial"],
            "note": f"Experiencia cercana: {candidate_years} años (requerido: {min_experience})",
            "candidate_years": candidate_years,
            "required_years": min_experience,
            "gap_years": round(min_experience - candidate_years, 1),
        }
    elif candidate_years >= min_experience * 0.5:  # Dentro del 50%
        return {
            "evaluator": "experience",
            "status": "no_cumple_importante",
            "value": KNOCKOUT_VALUES["no_cumple_importante"],
            "note": f"Experiencia insuficiente: {candidate_years} años (requerido: {min_experience})",
            "candidate_years": candidate_years,
            "required_years": min_experience,
            "gap_years": round(min_experience - candidate_years, 1),
        }
    else:
        return {
            "evaluator": "experience",
            "status": "no_cumple_fatal",
            "value": KNOCKOUT_VALUES["no_cumple_fatal"],
            "note": f"Experiencia muy por debajo: {candidate_years} años (requerido: {min_experience})",
            "candidate_years": candidate_years,
            "required_years": min_experience,
            "gap_years": round(min_experience - candidate_years, 1),
        }


def evaluate_salary_knockout(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None
) -> KnockoutResult:
    """
    Evalúa compatibilidad salarial.
    SIEMPRE devuelve "evidencia_insuficiente" porque salary_data no está poblado.
    
    Returns:
        KnockoutResult
    """
    # salary_data no está poblado en la BD actual (0% según diagnóstico)
    # Siempre devolver evidencia_insuficiente con nota explicativa
    
    candidate_salary = candidate.get("salary_data")
    job_salary_min = job.get("salary_min")
    job_salary_max = job.get("salary_max")
    
    return {
        "evaluator": "salary",
        "status": "evidencia_insuficiente",
        "value": KNOCKOUT_VALUES["evidencia_insuficiente"],
        "note": "salary_data no está poblado en el sistema - evaluación salarial omitida",
        "candidate_salary_data": candidate_salary,
        "job_salary_range": {
            "min": job_salary_min,
            "max": job_salary_max,
        } if job_salary_min or job_salary_max else None,
    }


# =============================================================================
# EVALUADOR PRINCIPAL
# =============================================================================

def evaluate_knockouts(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None
) -> KnockoutEvaluation:
    """
    Evalúa todos los knockouts y devuelve el factor K multiplicativo.
    
    Args:
        candidate: Diccionario del candidato
        job: Diccionario de la vacante
        scorecard: Scorecard opcional (para Fase 4)
    
    Returns:
        (K: float, results: List[KnockoutResult])
        K es el producto de todos los valores de knockout.
        Si algún knockout es fatal (0.00), K = 0.00.
    """
    results = []
    
    # Ejecutar todos los evaluadores
    evaluators = [
        evaluate_language_knockout,
        evaluate_location_knockout,
        evaluate_experience_knockout,
        evaluate_salary_knockout,
    ]
    
    for evaluator in evaluators:
        result = evaluator(candidate, job, scorecard)
        results.append(result)
    
    # Calcular K como producto de todos los valores
    K = 1.0
    for result in results:
        K *= result["value"]
    
    # Si K es 0, significa que hay un knockout fatal
    # Identificar cuál es
    fatal_knockouts = [r for r in results if r["value"] == 0.0]
    
    return (K, results)


# =============================================================================
# UTILIDADES DE RESUMEN
# =============================================================================

def summarize_knockouts(results: List[KnockoutResult]) -> Dict[str, Any]:
    """
    Resume los resultados de knockouts para visualización.
    
    Returns:
        Diccionario con resumen de knockouts
    """
    summary = {
        "total_evaluators": len(results),
        "passed": 0,
        "partial": 0,
        "failed": 0,
        "insufficient_evidence": 0,
        "fatal": False,
        "fatal_reasons": [],
        "warnings": [],
    }
    
    for result in results:
        status = result.get("status", "")
        
        if status == "cumple":
            summary["passed"] += 1
        elif status == "parcial":
            summary["partial"] += 1
            summary["warnings"].append({
                "evaluator": result.get("evaluator"),
                "note": result.get("note"),
            })
        elif status == "evidencia_insuficiente":
            summary["insufficient_evidence"] += 1
        elif status == "no_cumple_importante":
            summary["failed"] += 1
            summary["warnings"].append({
                "evaluator": result.get("evaluator"),
                "note": result.get("note"),
            })
        elif status == "no_cumple_fatal":
            summary["fatal"] = True
            summary["fatal_reasons"].append({
                "evaluator": result.get("evaluator"),
                "note": result.get("note"),
            })
    
    return summary
