"""
Scoring Engine v3 - Main Engine
Integra todos los componentes, knockouts, shrinkage y HEC para calcular HMS.

Fórmulas:
1. Componentes: cada uno devuelve (xi, ci, evidence)
2. Shrinkage: xi* = ci*xi + (1-ci)*0.52
3. A = Σ wi·xi* (media aritmética ponderada)
4. G = exp(Σ wi·ln(xi* + 0.01)) (media geométrica ponderada)
5. B = suma de boosts aplicables, cap 0.08
6. P = suma de penalties, cap 0.15
7. K = evaluate_knockouts (ya existe)
8. core = clamp(0.55*A + 0.45*G + B - P, 0.0, 1.0)
9. HEC = calculate_hec(candidate, components)
10. HMS = round(100 * K * core * (HEC ** 0.15))
"""
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from .config_v3 import (
    COMPONENT_WEIGHTS,
    COMPONENT_NAMES,
    SHRINKAGE_NEUTRAL,
    BOOST_CAP,
    PENALTY_CAP,
    HEC_EXPONENT,
)
from .components import (
    calculate_sk,
    calculate_er,
    calculate_fa,
    calculate_sa,
    calculate_ia,
    calculate_ed,
    calculate_tr,
    calculate_lo,
    calculate_sm,
    calculate_cq,
)
from .knockouts import evaluate_knockouts, summarize_knockouts
from .confidence import calculate_hec


# =============================================================================
# CONSTANTES
# =============================================================================

ENGINE_VERSION = "v3.0.0"


# =============================================================================
# TIPOS
# =============================================================================

ComponentScore = Dict[str, Any]  # {code, name, weight, raw, confidence, adjusted, evidence}
ScoreResult = Dict[str, Any]     # Resultado completo de score_v3


# =============================================================================
# BOOSTS
# =============================================================================

def calculate_boosts(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    component_scores: Dict[str, ComponentScore]
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Calcula boosts adicionales al score base.
    Cap máximo: BOOST_CAP (0.08)
    
    Boosts:
    - match exacto industria+función+seniority: +0.03
    - approved_by_recruiter: +0.02
    
    Returns:
        (total_boost, list of applied boosts)
    """
    boosts = []
    total = 0.0
    
    # Boost 1: Match exacto industria + función + seniority (+0.03)
    ia_raw = component_scores.get("IA", {}).get("raw", 0)
    fa_raw = component_scores.get("FA", {}).get("raw", 0)
    sa_raw = component_scores.get("SA", {}).get("raw", 0)
    
    # Considerar "exacto" cuando raw >= 0.95
    if ia_raw >= 0.95 and fa_raw >= 0.95 and sa_raw >= 0.95:
        boost_val = 0.03
        boosts.append({
            "name": "exact_match_industry_function_seniority",
            "value": boost_val,
            "reason": f"Match exacto: industria({ia_raw:.2f}), función({fa_raw:.2f}), seniority({sa_raw:.2f})"
        })
        total += boost_val
    
    # Boost 2: approved_by_recruiter (+0.02)
    ai_class = candidate.get("ai_classification", {})
    if ai_class.get("approved_by_recruiter", False):
        boost_val = 0.02
        boosts.append({
            "name": "approved_by_recruiter",
            "value": boost_val,
            "reason": "Candidato aprobado por reclutador"
        })
        total += boost_val
    
    # Aplicar cap
    total = min(total, BOOST_CAP)
    
    return (total, boosts)


# =============================================================================
# PENALTIES
# =============================================================================

def calculate_stability_penalty(candidate: Dict[str, Any]) -> Tuple[float, Optional[str]]:
    """
    Calcula penalty por inestabilidad laboral.
    Normalizada con max 0.04.
    
    Returns:
        (penalty_value, reason or None)
    """
    previous_companies = candidate.get("previous_companies", [])
    
    if not previous_companies or len(previous_companies) < 2:
        return (0.0, None)
    
    # Contar trabajos con duración < 1.5 años
    short_tenures = 0
    total_with_dates = 0
    
    for pc in previous_companies:
        start_date = pc.get("start_date")
        end_date = pc.get("end_date")
        
        if not start_date:
            continue
        
        total_with_dates += 1
        
        # Calcular duración
        try:
            if isinstance(start_date, str):
                start = datetime.strptime(start_date[:10], "%Y-%m-%d") if len(start_date) >= 10 else None
            else:
                start = start_date
            
            if not start:
                continue
            
            if end_date and str(end_date).strip().lower() not in ['', 'presente', 'actual', 'current', 'now']:
                if isinstance(end_date, str):
                    end = datetime.strptime(end_date[:10], "%Y-%m-%d") if len(end_date) >= 10 else datetime.now()
                else:
                    end = end_date
            else:
                end = datetime.now()
            
            years = (end - start).days / 365.25
            
            if years < 1.5:
                short_tenures += 1
                
        except (ValueError, TypeError):
            continue
    
    if total_with_dates < 2:
        return (0.0, None)
    
    # Ratio de trabajos cortos
    short_ratio = short_tenures / total_with_dates
    
    if short_ratio >= 0.6:
        return (0.04, f"Alta rotación: {short_tenures}/{total_with_dates} trabajos < 1.5 años")
    elif short_ratio >= 0.4:
        return (0.02, f"Rotación moderada: {short_tenures}/{total_with_dates} trabajos < 1.5 años")
    
    return (0.0, None)


def calculate_seniority_gap_penalty(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    component_scores: Dict[str, ComponentScore]
) -> Tuple[float, Optional[str]]:
    """
    Calcula penalties por sub/sobre-calificación en seniority.
    - Subcalificación >= 2 niveles: 0.04
    - Sobrecalificación >= 2 niveles: 0.03
    
    Returns:
        (penalty_value, reason or None)
    """
    sa_evidence = component_scores.get("SA", {}).get("evidence", {})
    
    cand_index = sa_evidence.get("candidate_index")
    job_index = sa_evidence.get("job_index")
    
    if cand_index is None or job_index is None:
        return (0.0, None)
    
    gap = cand_index - job_index
    
    # Subcalificado (candidato tiene menor seniority que el requerido)
    if gap <= -2:
        return (0.04, f"Subcalificación: candidato {abs(gap)} niveles por debajo")
    
    # Sobrecalificado (candidato tiene mayor seniority que el requerido)
    if gap >= 2:
        return (0.03, f"Sobrecalificación: candidato {gap} niveles por encima")
    
    return (0.0, None)


def calculate_penalties(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    component_scores: Dict[str, ComponentScore],
    knockout_results: List[Dict[str, Any]]
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Calcula penalties al score base.
    Cap máximo: PENALTY_CAP (0.15)
    
    Penalties:
    - calculate_stability_penalty existente normalizada, max 0.04
    - subcalificación >=2 niveles seniority: 0.04
    - sobrecalificación >=2 niveles: 0.03
    
    Returns:
        (total_penalty, list of applied penalties)
    """
    penalties = []
    total = 0.0
    
    # Penalty 1: Estabilidad laboral (max 0.04)
    stability_val, stability_reason = calculate_stability_penalty(candidate)
    if stability_val > 0:
        penalties.append({
            "name": "stability_penalty",
            "value": stability_val,
            "reason": stability_reason
        })
        total += stability_val
    
    # Penalty 2 y 3: Seniority gap
    seniority_val, seniority_reason = calculate_seniority_gap_penalty(candidate, job, component_scores)
    if seniority_val > 0:
        penalties.append({
            "name": "seniority_gap_penalty",
            "value": seniority_val,
            "reason": seniority_reason
        })
        total += seniority_val
    
    # Aplicar cap
    total = min(total, PENALTY_CAP)
    
    return (total, penalties)


# =============================================================================
# RECOMMENDED ACTION
# =============================================================================

def determine_recommended_action(
    hms: int,
    hec: float,
    K: float,
    component_scores: Dict[str, ComponentScore]
) -> str:
    """
    Determina la acción recomendada basada en HMS, HEC y contexto.
    
    Reglas (evaluadas en orden):
    1. K == 0 (fatal) → do_not_advance_knockout
    2. HMS >= 85 y HEC >= 0.75 → advance_to_screening
    3. HMS >= 75 → review_manually (sin condición de HEC)
    4. 65 <= HMS < 75 → possible_backup
    5. HMS < 65 y CQ >= 0.8 y FA < 0.4 → save_for_other_role
    6. else → low_priority
    
    Returns:
        recommended_action string
    """
    # 1. Fatal knockout
    if K == 0:
        return "do_not_advance_knockout"
    
    # 2. HMS >= 85 y HEC >= 0.75 → advance_to_screening
    if hms >= 85 and hec >= 0.75:
        return "advance_to_screening"
    
    # 3. HMS >= 75 → review_manually (score alto va a revisión humana)
    if hms >= 75:
        return "review_manually"
    
    # 4. 65 <= HMS < 75 → possible_backup
    if 65 <= hms < 75:
        return "possible_backup"
    
    # 5. HMS < 65 y CQ >= 0.8 y FA < 0.4 → guardar para otro rol
    if hms < 65:
        cq_raw = component_scores.get("CQ", {}).get("raw", 0)
        fa_raw = component_scores.get("FA", {}).get("raw", 0)
        
        if cq_raw >= 0.8 and fa_raw < 0.4:
            return "save_for_other_role"
    
    # 6. Default
    return "low_priority"


# =============================================================================
# FUNCIÓN PRINCIPAL: score_v3
# =============================================================================

def score_v3(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None
) -> ScoreResult:
    """
    Calcula el Humaniq Match Score v3 (HMS) para un candidato vs una vacante.
    
    Fórmula:
    1. Calcular 10 componentes (xi, ci)
    2. Shrinkage: xi* = ci * xi + (1 - ci) * 0.52
    3. A = Σ wi * xi* (media aritmética ponderada)
    4. G = exp(Σ wi * ln(xi* + 0.01)) (media geométrica ponderada)
    5. B = boosts, cap 0.08
    6. P = penalties, cap 0.15
    7. K = evaluate_knockouts
    8. core = clamp(0.55*A + 0.45*G + B - P, 0.0, 1.0)
    9. HEC = calculate_hec(candidate, components)
    10. HMS = round(100 * K * core * HEC^0.15)
    
    Args:
        candidate: Diccionario del candidato
        job: Diccionario de la vacante
        scorecard: Scorecard opcional (futuro)
    
    Returns:
        ScoreResult completo
    """
    # =========================================================================
    # 1. CALCULAR COMPONENTES
    # =========================================================================
    
    # Preparar skills
    cand_skills = candidate.get("skills", [])
    job_skills = job.get("required_skills", []) + job.get("preferred_skills", [])
    job_has_skills = bool(job_skills)
    
    # Calcular cada componente
    sk_xi, sk_ci, sk_ev = calculate_sk(cand_skills, job_skills, job_has_skills)
    er_xi, er_ci, er_ev = calculate_er(candidate, job)
    fa_xi, fa_ci, fa_ev = calculate_fa(candidate, job)
    sa_xi, sa_ci, sa_ev = calculate_sa(candidate, job)
    ia_xi, ia_ci, ia_ev = calculate_ia(candidate, job)
    ed_xi, ed_ci, ed_ev = calculate_ed(candidate)
    tr_xi, tr_ci, tr_ev = calculate_tr(candidate)
    lo_xi, lo_ci, lo_ev = calculate_lo(candidate, job)
    sm_xi, sm_ci, sm_ev = calculate_sm(
        candidate.get("embedding"),
        job.get("embedding")
    )
    cq_xi, cq_ci, cq_ev = calculate_cq(candidate)
    
    # Organizar en diccionario
    raw_components = {
        "SK": (sk_xi, sk_ci, sk_ev),
        "ER": (er_xi, er_ci, er_ev),
        "FA": (fa_xi, fa_ci, fa_ev),
        "SA": (sa_xi, sa_ci, sa_ev),
        "IA": (ia_xi, ia_ci, ia_ev),
        "ED": (ed_xi, ed_ci, ed_ev),
        "TR": (tr_xi, tr_ci, tr_ev),
        "LO": (lo_xi, lo_ci, lo_ev),
        "SM": (sm_xi, sm_ci, sm_ev),
        "CQ": (cq_xi, cq_ci, cq_ev),
    }
    
    # =========================================================================
    # 2. APLICAR SHRINKAGE
    # =========================================================================
    
    component_scores: Dict[str, ComponentScore] = {}
    
    for code, (xi, ci, ev) in raw_components.items():
        # Shrinkage: xi* = ci * xi + (1 - ci) * 0.52
        xi_adjusted = ci * xi + (1 - ci) * SHRINKAGE_NEUTRAL
        
        component_scores[code] = {
            "code": code,
            "name": COMPONENT_NAMES.get(code, code),
            "weight": COMPONENT_WEIGHTS[code],
            "raw": round(xi, 4),
            "confidence": round(ci, 4),
            "adjusted": round(xi_adjusted, 4),
            "evidence": ev,
        }
    
    # =========================================================================
    # 3. CALCULAR MEDIAS
    # =========================================================================
    
    # Media aritmética: A = Σ wi * xi*
    A = sum(
        COMPONENT_WEIGHTS[code] * cs["adjusted"]
        for code, cs in component_scores.items()
    )
    
    # Media geométrica: G = exp(Σ wi * ln(xi* + 0.01))
    log_sum = sum(
        COMPONENT_WEIGHTS[code] * math.log(cs["adjusted"] + 0.01)
        for code, cs in component_scores.items()
    )
    G = math.exp(log_sum)
    
    # =========================================================================
    # 4. KNOCKOUTS
    # =========================================================================
    
    K, knockout_results = evaluate_knockouts(candidate, job, scorecard)
    knockout_summary = summarize_knockouts(knockout_results)
    
    # =========================================================================
    # 5. BOOSTS Y PENALTIES
    # =========================================================================
    
    B, boosts_applied = calculate_boosts(candidate, job, component_scores)
    P, penalties_applied = calculate_penalties(candidate, job, component_scores, knockout_results)
    
    # =========================================================================
    # 6. CORE SCORE (con clamp a [0,1])
    # =========================================================================
    
    core_raw = 0.55 * A + 0.45 * G + B - P
    core = max(0.0, min(1.0, core_raw))
    
    # =========================================================================
    # 7. HEC
    # =========================================================================
    
    hec_score, hec_breakdown = calculate_hec(candidate, component_scores)
    
    # =========================================================================
    # 8. HMS FINAL
    # =========================================================================
    
    # HMS = round(100 * K * core * HEC^0.15)
    hms_raw = 100 * K * core * (hec_score ** HEC_EXPONENT)
    hms = round(hms_raw)
    
    # Clamp a [0, 100]
    hms = max(0, min(100, hms))
    
    # =========================================================================
    # 9. RECOMMENDED ACTION
    # =========================================================================
    
    recommended_action = determine_recommended_action(hms, hec_score, K, component_scores)
    
    # =========================================================================
    # 10. RESULTADO FINAL
    # =========================================================================
    
    return {
        "engine_version": ENGINE_VERSION,
        "match_score_v3": hms,
        "confidence_score": hec_score,
        
        "knockout_results": {
            "K": round(K, 4),
            "is_fatal": K == 0,
            "results": knockout_results,
            "summary": knockout_summary,
        },
        
        "component_breakdown": {
            code: {
                "raw": cs["raw"],
                "confidence": cs["confidence"],
                "adjusted": cs["adjusted"],
                "evidence": cs["evidence"],
            }
            for code, cs in component_scores.items()
        },
        
        "boosts": {
            "total": round(B, 4),
            "cap": BOOST_CAP,
            "applied": boosts_applied,
        },
        
        "penalties": {
            "total": round(P, 4),
            "cap": PENALTY_CAP,
            "applied": penalties_applied,
        },
        
        "recommended_action": recommended_action,
        
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        
        # Datos adicionales para debug
        "_debug": {
            "arithmetic_mean_A": round(A, 4),
            "geometric_mean_G": round(G, 4),
            "core_raw": round(core_raw, 4),
            "core_clamped": round(core, 4),
            "hms_raw": round(hms_raw, 4),
            "hec_factor": round(hec_score ** HEC_EXPONENT, 4),
        },
        
        # HEC breakdown
        "hec_breakdown": hec_breakdown,
        
        # Metadatos del candidato y job
        "candidate_id": str(candidate.get("_id", candidate.get("id", ""))),
        "candidate_name": candidate.get("full_name"),
        "job_id": str(job.get("_id", job.get("id", ""))),
        "job_title": job.get("title"),
    }


# =============================================================================
# UTILIDADES DE FORMATO
# =============================================================================

def format_score_report(result: ScoreResult) -> str:
    """
    Formatea un reporte legible del score para consola/debug.
    """
    lines = [
        "═" * 70,
        f"HUMANIQ MATCH SCORE {result['engine_version']}",
        "═" * 70,
        f"Candidato: {result['candidate_name']} (ID: {result['candidate_id']})",
        f"Vacante: {result['job_title']} (ID: {result['job_id']})",
        f"Fecha: {result['calculated_at']}",
        "",
        "─" * 70,
        f"HMS: {result['match_score_v3']}  |  HEC: {result['confidence_score']:.4f}  |  Acción: {result['recommended_action']}",
        "─" * 70,
        "",
        "COMPONENTES (10):",
        f"{'Código':<6} {'Nombre':<25} {'Raw':>8} {'CI':>8} {'Adj':>8} {'Peso':>6}",
        "-" * 70,
    ]
    
    for code in ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"]:
        cb = result["component_breakdown"].get(code, {})
        name = COMPONENT_NAMES.get(code, code)[:25]
        lines.append(
            f"{code:<6} {name:<25} {cb.get('raw', 0):>8.4f} {cb.get('confidence', 0):>8.4f} "
            f"{cb.get('adjusted', 0):>8.4f} {COMPONENT_WEIGHTS.get(code, 0):>6.2f}"
        )
    
    lines.extend([
        "",
        "AGREGACIÓN:",
        f"  A (aritmética): {result['_debug']['arithmetic_mean_A']:.4f}",
        f"  G (geométrica): {result['_debug']['geometric_mean_G']:.4f}",
        f"  Core raw: {result['_debug']['core_raw']:.4f}",
        f"  Core (clamped): {result['_debug']['core_clamped']:.4f}",
        "",
        f"KNOCKOUTS (K={result['knockout_results']['K']:.4f}):",
    ])
    
    for kr in result["knockout_results"]["results"]:
        criterion = kr.get('criterion', kr.get('evaluator', 'N/A'))
        k_val = kr.get('k_value')
        k_str = f"{k_val:.2f}" if k_val is not None else "N/A"
        lines.append(f"  - {criterion}: {kr['status']} (k={k_str}) - {kr.get('note', '')}")
    
    lines.extend([
        "",
        f"BOOSTS ({result['boosts']['total']:.4f} / cap {result['boosts']['cap']}):",
    ])
    for b in result["boosts"]["applied"]:
        lines.append(f"  + {b['name']}: +{b['value']:.3f} - {b['reason']}")
    if not result["boosts"]["applied"]:
        lines.append("  (ninguno)")
    
    lines.extend([
        "",
        f"PENALTIES ({result['penalties']['total']:.4f} / cap {result['penalties']['cap']}):",
    ])
    for p in result["penalties"]["applied"]:
        lines.append(f"  - {p['name']}: -{p['value']:.3f} - {p['reason']}")
    if not result["penalties"]["applied"]:
        lines.append("  (ninguno)")
    
    lines.extend([
        "",
        f"HEC BREAKDOWN (total: {result['confidence_score']:.4f}):",
    ])
    for signal, data in result["hec_breakdown"].items():
        lines.append(f"  {signal}: {data['score']:.4f} × {data['weight']:.2f} = {data['weighted']:.4f}")
    
    lines.extend([
        "",
        "═" * 70,
    ])
    
    return "\n".join(lines)
