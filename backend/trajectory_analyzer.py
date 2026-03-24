"""
Trajectory Analyzer
===================
Analiza trayectoria profesional, estabilidad laboral y nivel de experiencia funcional.
"""

from typing import Dict, List, Optional, Tuple, Any
from query_parser import infer_area_from_title, infer_seniority_from_title
from scoring_config import (
    EXPECTED_YEARS_BY_LEVEL,
    STABILITY_THRESHOLDS,
    MULTIPLICADORES_EXPERIENCIA,
    PENALTIES,
)


def calculate_experience_level(candidate: dict, query_area: str) -> str:
    """
    Determina el nivel de experiencia del candidato en el área buscada.
    
    Clasifica como:
    - "principal": Carrera construida en esta función (≥60% de trayectoria o área actual coincide)
    - "secundaria": Experiencia significativa (30-60% de trayectoria)
    - "marginal": Experiencia superficial (<30% de trayectoria)
    
    Args:
        candidate: Dict con datos del candidato
        query_area: Área funcional buscada
        
    Returns:
        Nivel de experiencia: "principal", "secundaria", o "marginal"
    """
    if not query_area:
        return "principal"  # Sin área específica, no penalizar
    
    current_area = candidate.get("functional_area", "")
    
    # REGLA PRINCIPAL: Si el área actual coincide exactamente, es "principal"
    # Esto asegura que un HR Executive rankeé como "principal" para búsqueda de HR
    if current_area and current_area.lower() == query_area.lower():
        return "principal"
    
    # Para los demás casos, analizar historial
    years_total = candidate.get("years_experience") or 1
    if years_total < 1:
        years_total = 1
    
    previous_companies = candidate.get("previous_companies", [])
    
    # Contar años en el área buscada
    years_in_area = 0
    
    # 1. Si área actual es adyacente
    if are_areas_adjacent(current_area, query_area):
        years_in_area += 1.5
    
    # 2. Revisar historial de empresas anteriores
    for company in previous_companies:
        title = company.get("title", "")
        years_at_company = company.get("years", 0)
        
        # Inferir área funcional del título
        inferred_area = infer_area_from_title(title)
        
        if inferred_area == query_area:
            years_in_area += years_at_company
        elif are_areas_adjacent(inferred_area, query_area):
            years_in_area += years_at_company * 0.3
    
    # 3. Calcular porcentaje de carrera en el área
    percentage = (years_in_area / years_total) * 100
    
    if percentage >= 60:
        return "principal"
    elif percentage >= 30:
        return "secundaria"
    else:
        return "marginal"


def are_areas_adjacent(area1: Optional[str], area2: Optional[str]) -> bool:
    """
    Verifica si dos áreas funcionales son adyacentes/relacionadas.
    """
    if not area1 or not area2:
        return False
    
    area1 = area1.lower()
    area2 = area2.lower()
    
    adjacent_pairs = {
        ("marketing", "sales"),
        ("sales", "marketing"),
        ("operations", "supply_chain"),
        ("supply_chain", "operations"),
        ("finance", "legal"),
        ("legal", "finance"),
        ("general_management", "operations"),
        ("operations", "general_management"),
    }
    
    return (area1, area2) in adjacent_pairs


def calculate_trajectory_score(candidate: dict) -> int:
    """
    Calcula el score de trayectoria del candidato (0-100).
    
    Componentes:
    - Años de experiencia vs nivel (25 puntos)
    - Progresión de carrera (25 puntos)
    - Duración promedio por empresa (25 puntos)
    - Consistencia funcional (25 puntos)
    
    Args:
        candidate: Dict con datos del candidato
        
    Returns:
        Score de 0-100
    """
    score = 0
    years_exp = candidate.get("years_experience") or 0
    seniority_index = get_seniority_index(candidate)
    previous_companies = candidate.get("previous_companies", [])
    
    # === 1. AÑOS DE EXPERIENCIA VS NIVEL (25 puntos) ===
    expected_range = EXPECTED_YEARS_BY_LEVEL.get(seniority_index, (0, 50))
    min_years, max_years = expected_range
    
    if min_years <= years_exp <= max_years:
        score += 25  # Experiencia coherente con nivel
    elif years_exp < min_years:
        score += 10  # Ascenso rápido (podría ser positivo o riesgoso)
    else:
        score += 15  # Más experiencia de la típica
    
    # === 2. PROGRESIÓN DE CARRERA (25 puntos) ===
    if len(previous_companies) >= 2:
        if has_ascending_progression(previous_companies):
            score += 25  # Carrera con ascensos claros
        elif has_lateral_moves(previous_companies):
            score += 15  # Movimientos laterales (especialización)
        else:
            score += 5   # Sin progresión clara
    else:
        score += 10  # Poca historia laboral visible
    
    # === 3. DURACIÓN PROMEDIO POR EMPRESA (25 puntos) ===
    avg_tenure = calculate_average_tenure(previous_companies, years_exp)
    
    if avg_tenure >= 4:
        score += 25  # Muy estable (4+ años promedio)
    elif avg_tenure >= 2.5:
        score += 20  # Buena estabilidad (2.5-4 años)
    elif avg_tenure >= 1.5:
        score += 10  # Estabilidad moderada (1.5-2.5 años)
    else:
        score += 0   # Alta rotación (<1.5 años promedio)
    
    # === 4. CONSISTENCIA FUNCIONAL (25 puntos) ===
    current_area = candidate.get("functional_area")
    consistency = calculate_functional_consistency(previous_companies, current_area)
    
    if consistency >= 0.8:
        score += 25  # Carrera muy consistente en el área
    elif consistency >= 0.5:
        score += 15  # Carrera mayormente en el área
    elif consistency >= 0.3:
        score += 10  # Algo de experiencia en el área
    else:
        score += 5   # Carrera diversa / cambio de área
    
    return min(100, score)


def calculate_stability_score(candidate: dict) -> Tuple[int, str, str]:
    """
    Calcula score de estabilidad laboral y nivel de alerta.
    
    Args:
        candidate: Dict con datos del candidato
        
    Returns:
        Tuple de (score: 0-100, warning_level: str, detail: str)
    """
    years_exp = candidate.get("years_experience") or 0
    previous_companies = candidate.get("previous_companies", [])
    
    if years_exp == 0:
        return (50, "none", "Sin datos de experiencia")
    
    # Contar empleos totales (anteriores + actual)
    num_jobs = len(previous_companies) + 1
    
    # Ratio de empleos por año
    ratio = num_jobs / max(years_exp, 1)
    
    # Calcular score y warning
    if ratio <= STABILITY_THRESHOLDS["very_stable"]:
        score = 100
        warning = "none"
        detail = f"{num_jobs} empleos en {years_exp} años - muy estable"
    elif ratio <= STABILITY_THRESHOLDS["stable"]:
        score = 85
        warning = "none"
        detail = f"{num_jobs} empleos en {years_exp} años - estable"
    elif ratio <= STABILITY_THRESHOLDS["moderate"]:
        score = 60
        warning = "low"
        detail = f"{num_jobs} empleos en {years_exp} años - moderado"
    elif ratio <= STABILITY_THRESHOLDS["concerning"]:
        score = 40
        warning = "moderate"
        detail = f"{num_jobs} empleos en {years_exp} años - rotación frecuente"
    else:
        score = 20
        warning = "high"
        detail = f"{num_jobs} empleos en {years_exp} años - alta rotación"
    
    return (score, warning, detail)


def calculate_stability_penalty(warning_level: str) -> int:
    """
    Calcula el penalty de estabilidad basado en nivel de alerta.
    """
    penalties = {
        "none": 0,
        "low": PENALTIES.get("estabilidad_low", 2),
        "moderate": PENALTIES.get("estabilidad_moderate", 5),
        "high": PENALTIES.get("estabilidad_high", 10),
    }
    return penalties.get(warning_level, 0)


def get_seniority_index(candidate: dict) -> int:
    """
    Obtiene el índice de seniority del candidato (1-12).
    """
    # Primero intentar con el campo seniority
    seniority = candidate.get("seniority", "")
    
    SENIORITY_MAP = {
        "entry": 1,
        "intern": 1,
        "junior": 3,
        "mid": 4,
        "senior": 6,
        "lead": 6,
        "manager": 7,
        "senior_manager": 8,
        "director": 9,
        "vp": 10,
        "c_level": 11,
    }
    
    if seniority:
        mapped = SENIORITY_MAP.get(seniority.lower(), None)
        if mapped:
            return mapped
    
    # Si no hay seniority, inferir del título actual
    current_title = candidate.get("current_title", "")
    if current_title:
        inferred = infer_seniority_from_title(current_title)
        if inferred:
            return inferred
    
    # Default a nivel manager
    return 7


def has_ascending_progression(companies: List[dict]) -> bool:
    """
    Verifica si hubo progresión ascendente en la trayectoria.
    """
    if len(companies) < 2:
        return False
    
    levels = []
    for company in companies:
        title = company.get("title", "")
        level = infer_seniority_from_title(title)
        if level:
            levels.append(level)
    
    if len(levels) < 2:
        return False
    
    # Contar ascensos
    ascents = sum(1 for i in range(1, len(levels)) if levels[i] > levels[i-1])
    
    # Al menos la mitad deben ser ascensos
    return ascents >= len(levels) // 2


def has_lateral_moves(companies: List[dict]) -> bool:
    """
    Verifica si los movimientos fueron laterales (especialización).
    """
    if len(companies) < 2:
        return False
    
    levels = []
    for company in companies:
        title = company.get("title", "")
        level = infer_seniority_from_title(title)
        if level:
            levels.append(level)
    
    if len(levels) < 2:
        return True  # Sin datos, asumir lateral
    
    # Calcular variación
    avg_level = sum(levels) / len(levels)
    variance = sum((level - avg_level) ** 2 for level in levels) / len(levels)
    
    # Si varianza es baja, son movimientos laterales
    return variance < 2


def calculate_average_tenure(companies: List[dict], total_years: int) -> float:
    """
    Calcula duración promedio en cada empresa.
    """
    if not companies:
        return total_years  # Si no hay historial, asumir todo en una empresa
    
    num_companies = len(companies) + 1  # +1 por empresa actual
    
    return total_years / num_companies if num_companies > 0 else 0


def calculate_functional_consistency(companies: List[dict], current_area: Optional[str]) -> float:
    """
    Calcula qué porcentaje de la carrera fue en el área actual.
    Retorna valor entre 0.0 y 1.0.
    """
    if not current_area:
        return 0.5  # Sin área actual, valor neutral
    
    total_positions = len(companies) + 1  # +1 por posición actual
    matching_positions = 1  # La actual ya cuenta
    
    current_area = current_area.lower()
    
    for company in companies:
        title = company.get("title", "")
        inferred = infer_area_from_title(title)
        
        if inferred and inferred.lower() == current_area:
            matching_positions += 1
        elif inferred and are_areas_adjacent(inferred, current_area):
            matching_positions += 0.5  # Áreas adyacentes cuentan parcialmente
    
    return matching_positions / total_positions


def estimate_professional_stage(candidate: dict) -> str:
    """
    Estima la etapa profesional del candidato.
    
    Returns:
        "early_career", "developing", "mid_career", "senior", o "executive"
    """
    years = candidate.get("years_experience", 0)
    
    if years <= 3:
        return "early_career"
    elif years <= 8:
        return "developing"
    elif years <= 15:
        return "mid_career"
    elif years <= 25:
        return "senior"
    else:
        return "executive"


def calculate_gm_evidence(candidate: dict, query_area: str) -> str:
    """
    Para candidatos de General Management, evalúa si tienen evidencia
    funcional en el área buscada.
    
    Returns:
        "fuerte", "moderada", "débil", o "ninguna"
    """
    if not query_area:
        return "fuerte"  # Sin área específica, no penalizar
    
    points = 0
    previous_companies = candidate.get("previous_companies", [])
    skills = candidate.get("skills", [])
    ai_summary = candidate.get("ai_summary", "")
    
    # 1. Revisar títulos anteriores
    for company in previous_companies:
        title = company.get("title", "")
        years = company.get("years", 0)
        
        inferred_area = infer_area_from_title(title)
        
        if inferred_area == query_area:
            if years >= 5:
                points += 40  # Trayectoria significativa
            elif years >= 3:
                points += 25
            elif years >= 1:
                points += 10
    
    # 2. Revisar skills relevantes
    area_skill_keywords = get_area_skill_keywords(query_area)
    for skill in skills:
        skill_lower = skill.lower()
        for keyword in area_skill_keywords:
            if keyword in skill_lower:
                points += 5
                break
    
    # 3. Revisar AI summary
    if ai_summary and query_area:
        area_keywords = get_area_keywords(query_area)
        summary_lower = ai_summary.lower()
        for keyword in area_keywords:
            if keyword in summary_lower:
                points += 8
                break
    
    # Clasificar evidencia
    if points >= 50:
        return "fuerte"
    elif points >= 30:
        return "moderada"
    elif points >= 10:
        return "débil"
    else:
        return "ninguna"


def get_area_skill_keywords(area: str) -> List[str]:
    """
    Retorna keywords de skills típicos del área.
    """
    keywords = {
        "human_resources": ["reclutamiento", "compensaciones", "talento", "capacitación", "nómina", "hr", "hris"],
        "finance": ["finanzas", "contabilidad", "auditoría", "presupuesto", "fp&a", "tesorería", "fiscal"],
        "operations": ["lean", "six sigma", "producción", "manufactura", "mejora continua", "calidad"],
        "supply_chain": ["logística", "supply chain", "s&op", "inventario", "compras", "procurement"],
        "marketing": ["marketing", "branding", "digital", "seo", "sem", "crm", "growth"],
        "sales": ["ventas", "crm", "negociación", "key account", "business development"],
        "technology": ["software", "programación", "cloud", "data", "devops", "agile", "scrum"],
        "legal": ["derecho", "contratos", "compliance", "regulatorio", "corporativo"],
    }
    return keywords.get(area, [])


def get_area_keywords(area: str) -> List[str]:
    """
    Retorna keywords generales del área para buscar en texto.
    """
    keywords = {
        "human_resources": ["recursos humanos", "rh", "hr", "talento", "people"],
        "finance": ["finanzas", "financiero", "contable", "fiscal"],
        "operations": ["operaciones", "producción", "manufactura", "planta"],
        "supply_chain": ["supply chain", "cadena de suministro", "logística", "compras"],
        "marketing": ["marketing", "mercadotecnia", "marca", "digital"],
        "sales": ["ventas", "comercial", "cliente", "revenue"],
        "technology": ["tecnología", "sistemas", "software", "datos"],
        "legal": ["legal", "jurídico", "compliance", "contratos"],
    }
    return keywords.get(area, [])
