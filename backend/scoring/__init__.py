"""
Scoring Engine v3
Motor de scoring aislado para evaluación de candidatos.

Módulos:
- config_v3: Pesos, constantes y valores de knockout
- components: 10 funciones de componentes (SK, ER, FA, SA, IA, ED, TR, LO, SM, CQ)
- knockouts: Evaluadores de requisitos mínimos
"""
from .config_v3 import (
    COMPONENT_WEIGHTS,
    COMPONENT_NAMES,
    KNOCKOUT_VALUES,
    SHRINKAGE_NEUTRAL,
    SEMANTIC_THRESHOLD,
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

from .knockouts import (
    evaluate_knockouts,
    evaluate_language_knockout,
    evaluate_location_knockout,
    evaluate_experience_knockout,
    evaluate_salary_knockout,
    summarize_knockouts,
)

__all__ = [
    # Config
    "COMPONENT_WEIGHTS",
    "COMPONENT_NAMES",
    "KNOCKOUT_VALUES",
    "SHRINKAGE_NEUTRAL",
    "SEMANTIC_THRESHOLD",
    # Components
    "calculate_sk",
    "calculate_er",
    "calculate_fa",
    "calculate_sa",
    "calculate_ia",
    "calculate_ed",
    "calculate_tr",
    "calculate_lo",
    "calculate_sm",
    "calculate_cq",
    # Knockouts
    "evaluate_knockouts",
    "evaluate_language_knockout",
    "evaluate_location_knockout",
    "evaluate_experience_knockout",
    "evaluate_salary_knockout",
    "summarize_knockouts",
]
