"""
Scoring Engine v3 - Knockouts
Evaluadores de knockout que determinan si un candidato cumple requisitos mínimos.

REGLA GENERAL: Un criterio que la vacante NO define, NO APLICA y NO castiga.
- status: "no_aplica"
- k_value: None (no entra al producto de K)
"""
import re
from typing import Tuple, List, Dict, Any, Optional

from .config_v3 import KNOCKOUT_VALUES


# Tipo de retorno para evaluadores individuales
KnockoutResult = Dict[str, Any]  # {"criterion": str, "status": str, "k_value": float|None, ...}

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
    
    Si la vacante NO define required_languages → NO APLICA (k_value=None)
    """
    required_languages = job.get("required_languages", [])
    
    # Si la vacante no especifica idiomas, el criterio NO APLICA
    if not required_languages:
        return {
            "criterion": "language",
            "status": "no_aplica",
            "k_value": None,
            "note": "Vacante sin requisito de idiomas",
        }
    
    candidate_languages = candidate.get("languages", [])
    
    # Si el candidato no tiene idiomas registrados
    if not candidate_languages:
        return {
            "criterion": "language",
            "status": "evidencia_insuficiente",
            "k_value": KNOCKOUT_VALUES["evidencia_insuficiente"],
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
            "criterion": "language",
            "status": "cumple",
            "k_value": KNOCKOUT_VALUES["cumple"],
            "note": "Todos los idiomas requeridos presentes",
            "required": required_languages,
            "matched": matched,
            "missing": [],
            "candidate_languages": candidate_languages,
        }
    elif len(matched) > 0:
        return {
            "criterion": "language",
            "status": "parcial",
            "k_value": KNOCKOUT_VALUES["parcial"],
            "note": f"Faltan idiomas: {', '.join(missing)}",
            "required": required_languages,
            "matched": matched,
            "missing": missing,
            "candidate_languages": candidate_languages,
        }
    else:
        return {
            "criterion": "language",
            "status": "no_cumple_importante",
            "k_value": KNOCKOUT_VALUES["no_cumple_importante"],
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
    
    Si work_scheme es remoto → NO APLICA
    Si la vacante no especifica city/state → NO APLICA
    """
    work_scheme = job.get("work_scheme", "").lower()
    
    # Si es remoto, el criterio de ubicación NO APLICA
    if work_scheme in ["remoto", "remote", "full_remote", "100% remoto"]:
        return {
            "criterion": "location",
            "status": "no_aplica",
            "k_value": None,
            "note": "Posición remota - ubicación no es criterio de knockout",
            "work_scheme": work_scheme,
        }
    
    job_city = (job.get("city") or "").strip().lower()
    job_state = (job.get("state") or "").strip().lower()
    
    # Si la vacante no especifica ubicación, el criterio NO APLICA
    if not job_city and not job_state:
        return {
            "criterion": "location",
            "status": "no_aplica",
            "k_value": None,
            "note": "Vacante sin requisito de ubicación específica",
            "work_scheme": work_scheme or "presencial",
        }
    
    # Si es híbrido, ubicación es importante pero no fatal
    is_hybrid = work_scheme in ["híbrido", "hybrid", "hibrido"]
    
    cand_city = (candidate.get("city") or "").strip().lower()
    cand_state = (candidate.get("state") or "").strip().lower()
    
    # Si el candidato no tiene ubicación registrada
    if not cand_city and not cand_state:
        return {
            "criterion": "location",
            "status": "evidencia_insuficiente",
            "k_value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": "Candidato sin ubicación registrada",
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }
    
    # Comparar ubicaciones
    same_city = job_city and cand_city and job_city == cand_city
    same_state = job_state and cand_state and job_state == cand_state
    
    if same_city:
        return {
            "criterion": "location",
            "status": "cumple",
            "k_value": KNOCKOUT_VALUES["cumple"],
            "note": "Misma ciudad",
            "candidate_location": {"city": cand_city, "state": cand_state},
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }
    elif same_state:
        status = "cumple" if is_hybrid else "parcial"
        return {
            "criterion": "location",
            "status": status,
            "k_value": KNOCKOUT_VALUES[status],
            "note": "Mismo estado, diferente ciudad",
            "candidate_location": {"city": cand_city, "state": cand_state},
            "job_location": {"city": job_city, "state": job_state},
            "work_scheme": work_scheme or "presencial",
        }
    else:
        # Diferente ubicación
        status = "parcial" if is_hybrid else "no_cumple_importante"
        return {
            "criterion": "location",
            "status": status,
            "k_value": KNOCKOUT_VALUES[status],
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
    
    Si la vacante NO define min_experience → NO APLICA
    """
    min_experience = job.get("min_experience")
    
    # Si la vacante no especifica experiencia mínima, el criterio NO APLICA
    if not min_experience or min_experience <= 0:
        return {
            "criterion": "experience",
            "status": "no_aplica",
            "k_value": None,
            "note": "Vacante sin requisito de experiencia mínima",
        }
    
    candidate_years = candidate.get("years_experience")
    
    # Si el candidato no tiene años de experiencia registrados
    if candidate_years is None:
        return {
            "criterion": "experience",
            "status": "evidencia_insuficiente",
            "k_value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": "Candidato sin años de experiencia registrados",
            "required_years": min_experience,
        }
    
    # Comparar experiencia
    if candidate_years >= min_experience:
        return {
            "criterion": "experience",
            "status": "cumple",
            "k_value": KNOCKOUT_VALUES["cumple"],
            "note": f"Experiencia suficiente: {candidate_years} >= {min_experience} años",
            "candidate_years": candidate_years,
            "required_years": min_experience,
        }
    elif candidate_years >= min_experience * 0.8:  # Dentro del 80%
        return {
            "criterion": "experience",
            "status": "parcial",
            "k_value": KNOCKOUT_VALUES["parcial"],
            "note": f"Experiencia cercana: {candidate_years} años (requerido: {min_experience})",
            "candidate_years": candidate_years,
            "required_years": min_experience,
            "gap_years": round(min_experience - candidate_years, 1),
        }
    elif candidate_years >= min_experience * 0.5:  # Dentro del 50%
        return {
            "criterion": "experience",
            "status": "no_cumple_importante",
            "k_value": KNOCKOUT_VALUES["no_cumple_importante"],
            "note": f"Experiencia insuficiente: {candidate_years} años (requerido: {min_experience})",
            "candidate_years": candidate_years,
            "required_years": min_experience,
            "gap_years": round(min_experience - candidate_years, 1),
        }
    else:
        return {
            "criterion": "experience",
            "status": "no_cumple_fatal",
            "k_value": KNOCKOUT_VALUES["no_cumple_fatal"],
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
    
    Si la vacante NO define restricción salarial (compensation_constraints null,
    salary_min/max vacíos) → NO APLICA (k_value=None)
    
    Si la vacante SÍ define restricción y el candidato no tiene salary_data
    parseable → evidencia_insuficiente (0.85)
    
    Si ambos datos existen → evaluar cumple/parcial/no_cumple
    """
    # Obtener restricciones salariales de la vacante
    compensation_constraints = job.get("compensation_constraints")
    job_salary_min = job.get("salary_min")
    job_salary_max = job.get("salary_max")
    
    # Determinar si la vacante tiene restricción salarial definida
    has_salary_constraint = (
        compensation_constraints is not None or
        (job_salary_min is not None and job_salary_min > 0) or
        (job_salary_max is not None and job_salary_max > 0)
    )
    
    # Si la vacante NO define restricción salarial, el criterio NO APLICA
    if not has_salary_constraint:
        return {
            "criterion": "salary",
            "status": "no_aplica",
            "k_value": None,
            "note": "Vacante sin restricción salarial definida",
        }
    
    # La vacante SÍ tiene restricción, verificar datos del candidato
    candidate_salary = candidate.get("salary_data") or candidate.get("expected_salary")
    
    # Si el candidato no tiene salary_data parseable
    if not candidate_salary:
        return {
            "criterion": "salary",
            "status": "evidencia_insuficiente",
            "k_value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": "Candidato sin datos salariales - no se puede evaluar compatibilidad",
            "job_salary_range": {
                "min": job_salary_min,
                "max": job_salary_max,
            },
        }
    
    # Ambos tienen datos, evaluar compatibilidad
    # Intentar obtener el valor numérico del salario del candidato
    try:
        if isinstance(candidate_salary, dict):
            cand_min = candidate_salary.get("min") or candidate_salary.get("expected") or 0
            cand_max = candidate_salary.get("max") or cand_min
        elif isinstance(candidate_salary, (int, float)):
            cand_min = cand_max = candidate_salary
        else:
            # No se puede parsear
            return {
                "criterion": "salary",
                "status": "evidencia_insuficiente",
                "k_value": KNOCKOUT_VALUES["evidencia_insuficiente"],
                "note": "Formato de salary_data no reconocido",
                "candidate_salary_data": candidate_salary,
            }
        
        # Evaluar compatibilidad
        # Cumple: el rango del candidato está dentro del rango de la vacante
        # Parcial: hay solapamiento parcial
        # No cumple: no hay solapamiento
        
        job_min = job_salary_min or 0
        job_max = job_salary_max or float('inf')
        
        # Verificar solapamiento
        if cand_max < job_min:
            # Candidato pide menos del mínimo (raro pero posible)
            return {
                "criterion": "salary",
                "status": "cumple",
                "k_value": KNOCKOUT_VALUES["cumple"],
                "note": f"Expectativa salarial ({cand_max}) dentro del presupuesto",
                "candidate_salary": {"min": cand_min, "max": cand_max},
                "job_salary_range": {"min": job_min, "max": job_max},
            }
        elif cand_min > job_max:
            # Candidato pide más del máximo
            gap = cand_min - job_max
            gap_percent = (gap / job_max * 100) if job_max > 0 else 100
            
            if gap_percent <= 15:
                return {
                    "criterion": "salary",
                    "status": "parcial",
                    "k_value": KNOCKOUT_VALUES["parcial"],
                    "note": f"Expectativa salarial {gap_percent:.0f}% sobre presupuesto",
                    "candidate_salary": {"min": cand_min, "max": cand_max},
                    "job_salary_range": {"min": job_min, "max": job_max},
                }
            else:
                return {
                    "criterion": "salary",
                    "status": "no_cumple_importante",
                    "k_value": KNOCKOUT_VALUES["no_cumple_importante"],
                    "note": f"Expectativa salarial {gap_percent:.0f}% sobre presupuesto",
                    "candidate_salary": {"min": cand_min, "max": cand_max},
                    "job_salary_range": {"min": job_min, "max": job_max},
                }
        else:
            # Hay solapamiento
            return {
                "criterion": "salary",
                "status": "cumple",
                "k_value": KNOCKOUT_VALUES["cumple"],
                "note": "Expectativa salarial compatible con presupuesto",
                "candidate_salary": {"min": cand_min, "max": cand_max},
                "job_salary_range": {"min": job_min, "max": job_max},
            }
            
    except Exception as e:
        return {
            "criterion": "salary",
            "status": "evidencia_insuficiente",
            "k_value": KNOCKOUT_VALUES["evidencia_insuficiente"],
            "note": f"Error evaluando salary: {str(e)}",
            "candidate_salary_data": candidate_salary,
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
    
    REGLA: Criterios con status="no_aplica" (k_value=None) NO entran al producto de K.
    
    Args:
        candidate: Diccionario del candidato
        job: Diccionario de la vacante
        scorecard: Scorecard opcional (para Fase 4)
    
    Returns:
        (K: float, results: List[KnockoutResult])
        K es el producto de los valores de knockout que SÍ aplican.
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
    
    # Calcular K como producto de los valores que SÍ aplican (k_value != None)
    K = 1.0
    applicable_count = 0
    
    for result in results:
        k_value = result.get("k_value")
        if k_value is not None:
            K *= k_value
            applicable_count += 1
    
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
        "applicable": 0,
        "not_applicable": 0,
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
        k_value = result.get("k_value")
        
        if status == "no_aplica" or k_value is None:
            summary["not_applicable"] += 1
        elif status == "cumple":
            summary["applicable"] += 1
            summary["passed"] += 1
        elif status == "parcial":
            summary["applicable"] += 1
            summary["partial"] += 1
            summary["warnings"].append({
                "criterion": result.get("criterion"),
                "note": result.get("note"),
            })
        elif status == "evidencia_insuficiente":
            summary["applicable"] += 1
            summary["insufficient_evidence"] += 1
        elif status == "no_cumple_importante":
            summary["applicable"] += 1
            summary["failed"] += 1
            summary["warnings"].append({
                "criterion": result.get("criterion"),
                "note": result.get("note"),
            })
        elif status == "no_cumple_fatal":
            summary["applicable"] += 1
            summary["fatal"] = True
            summary["fatal_reasons"].append({
                "criterion": result.get("criterion"),
                "note": result.get("note"),
            })
    
    return summary
