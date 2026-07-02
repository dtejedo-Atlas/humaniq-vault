"""
Scoring Engine v3 - Configuration
Pesos, constantes y valores de knockout para el motor de scoring v3.
"""
from typing import Dict

# =============================================================================
# PESOS DE COMPONENTES (deben sumar 1.0)
# =============================================================================
COMPONENT_WEIGHTS: Dict[str, float] = {
    "SK": 0.16,  # Skills coverage
    "ER": 0.15,  # Experience relevance (años en el área)
    "FA": 0.13,  # Functional affinity
    "SA": 0.12,  # Seniority alignment
    "IA": 0.11,  # Industry affinity
    "ED": 0.10,  # Executive depth
    "TR": 0.08,  # Trajectory score
    "LO": 0.06,  # Location fit
    "SM": 0.05,  # Semantic similarity
    "CQ": 0.04,  # CV quality / completeness
}

# Validación: los pesos DEBEN sumar 1.0
_weight_sum = sum(COMPONENT_WEIGHTS.values())
assert abs(_weight_sum - 1.0) < 1e-9, f"COMPONENT_WEIGHTS must sum to 1.0, got {_weight_sum}"


# =============================================================================
# CONSTANTES DEL MOTOR
# =============================================================================
SHRINKAGE_NEUTRAL = 0.52       # Valor neutral para componentes sin confianza
GEO_EPSILON = 0.01             # Epsilon para comparaciones geográficas
HEC_EXPONENT = 0.15            # Exponente para Hierarchical Exponential Combination
BOOST_CAP = 0.08               # Cap máximo para boosts
PENALTY_CAP = 0.15             # Cap máximo para penalizaciones
SEMANTIC_THRESHOLD = 0.20      # Umbral mínimo de similitud semántica para remapeo


# =============================================================================
# VALORES DE KNOCKOUT
# =============================================================================
KNOCKOUT_VALUES: Dict[str, float] = {
    "cumple": 1.00,
    "evidencia_insuficiente": 0.85,
    "parcial": 0.70,
    "no_cumple_importante": 0.50,
    "no_cumple_fatal": 0.00,
}


# =============================================================================
# MAPEO DE COMPONENTES A NOMBRES LEGIBLES
# =============================================================================
COMPONENT_NAMES: Dict[str, str] = {
    "SK": "Skills Coverage",
    "ER": "Experience Relevance",
    "FA": "Functional Affinity",
    "SA": "Seniority Alignment",
    "IA": "Industry Affinity",
    "ED": "Executive Depth",
    "TR": "Trajectory Score",
    "LO": "Location Fit",
    "SM": "Semantic Similarity",
    "CQ": "CV Quality",
}


# =============================================================================
# CONFIGURACIÓN DE EXPERIENCE RELEVANCE (ER)
# =============================================================================
ER_CONFIG = {
    "default_min_years": 5,      # Si la vacante no especifica min_experience
    "max_years_cap": 20,         # Cap para normalización
    "current_job_weight": 1.2,   # Peso extra para empleo actual
}


# =============================================================================
# CONFIGURACIÓN DE EXECUTIVE DEPTH (ED)
# =============================================================================
ED_CONFIG = {
    "seniority_weight": 0.6,     # Peso del seniority actual
    "history_weight": 0.4,       # Peso de historial ejecutivo
    "max_seniority_index": 9,    # c_level = 9
    "executive_titles": [        # Títulos considerados ejecutivos (director+)
        "director", "vp", "c_level", "ceo", "cfo", "coo", "cto", "cmo",
        "vice president", "vicepresidente", "chief", "president", "presidente"
    ],
}


# =============================================================================
# CONFIGURACIÓN DE LOCATION (LO)
# =============================================================================
LO_CONFIG = {
    "remote_score": 1.0,         # Score automático si work_scheme = remoto
    "same_city_score": 1.0,      # Score si coincide ciudad
    "same_state_score": 0.7,     # Score si coincide estado pero no ciudad
    "different_location": 0.3,   # Score si no coincide ubicación
    "missing_data_score": 0.5,   # Score cuando faltan datos de ubicación
    "missing_data_confidence": 0.3,  # Confianza cuando faltan datos
}


# =============================================================================
# CONFIGURACIÓN DE CV QUALITY (CQ)
# =============================================================================
CQ_CRITICAL_FIELDS = [
    "email",
    "phone", 
    "current_title",
    "skills_min_3",              # skills con al menos 3 elementos
    "previous_companies_min_1",  # al menos 1 empresa previa
    "previous_companies_dates",  # empresas con fechas
    "languages_min_1",           # al menos 1 idioma
    "years_experience",          # años de experiencia definidos
]
