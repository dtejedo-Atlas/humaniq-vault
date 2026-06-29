"""
Scoring Configuration v2.2
===========================
Configuración centralizada de pesos, thresholds y penalties para el sistema de ranking.

IMPORTANTE: Este archivo es la ÚNICA fuente de verdad para los pesos de scoring.
No definir pesos en otros archivos - importarlos desde aquí.
"""

# =============================================================================
# PESOS DE SCORING - DOS SISTEMAS PARA DIFERENTES CASOS DE USO
# =============================================================================
#
# ¿Por qué hay dos sets de pesos?
# --------------------------------
# 
# 1. SEARCH_WEIGHTS (búsqueda libre):
#    - Se usa cuando el usuario escribe una query de texto libre (ej: "CFO fintech")
#    - El peso semántico es MAYOR (0.13) porque la query es ambigua y necesitamos
#      interpretar la intención del usuario usando embeddings
#    - No hay skills explícitos ni requisitos de experiencia definidos
#
# 2. JOB_MATCH_WEIGHTS (match contra vacante):
#    - Se usa cuando matcheamos candidatos contra una vacante específica
#    - La vacante tiene skills requeridos y años de experiencia explícitos
#    - El peso de skills (0.12) y experiencia (0.08) son mayores porque están definidos
#    - El peso semántico es MENOR (0.05) porque ya tenemos criterios estructurados
#
# =============================================================================

# Pesos para BÚSQUEDA LIBRE (query de texto)
# El usuario escribe algo como "gerente de operaciones automotriz"
SEARCH_WEIGHTS = {
    "funcional": 0.40,      # Área funcional principal - mayor peso
    "seniority": 0.20,      # Nivel jerárquico correcto
    "industria": 0.15,      # Coincidencia de industria
    "semantico": 0.13,      # Similitud semántica - MAYOR porque la query es ambigua
    "trayectoria": 0.05,    # Progresión y consistencia de carrera
    "keywords": 0.05,       # Match textual directo
    "estabilidad": 0.02,    # Análisis de rotación laboral
}

# Alias para compatibilidad con código existente
WEIGHTS = SEARCH_WEIGHTS

# Verificar que suman 100%
assert abs(sum(SEARCH_WEIGHTS.values()) - 1.0) < 0.001, "SEARCH_WEIGHTS deben sumar 1.0"


# Pesos para JOB MATCHING (match contra vacante específica)
# La vacante tiene required_skills, years_experience, etc. definidos explícitamente
JOB_MATCH_WEIGHTS = {
    "funcional": 0.35,      # Área funcional (ligeramente menor, skills compensan)
    "seniority": 0.20,      # Nivel jerárquico - igual de importante
    "industria": 0.15,      # Industria - igual de importante
    "skills": 0.12,         # Skills match - MAYOR porque la vacante los define explícitamente
    "experiencia": 0.08,    # Años de experiencia - MAYOR porque la vacante lo especifica
    "semantico": 0.05,      # Similitud semántica - MENOR porque ya hay criterios estructurados
    "trayectoria": 0.05,    # Consistencia de carrera
}

# Verificar que suman 100%
assert abs(sum(JOB_MATCH_WEIGHTS.values()) - 1.0) < 0.001, "JOB_MATCH_WEIGHTS deben sumar 1.0"


# Threshold mínimo para incluir en resultados de job matching
JOB_MATCH_THRESHOLD = 60


# ============= THRESHOLDS =============

# Score mínimo para incluir en resultados (0-100)
MIN_MATCH_SCORE = 60

# Threshold de similitud semántica (0.0-1.0)
SEMANTIC_THRESHOLD = 0.40

# Máximo de resultados a retornar
MAX_RESULTS = 30


# ============= BOOSTS (POSITIVOS) =============

BOOSTS = {
    "match_exacto_funcion": 12,      # Área funcional = área de query
    "match_exacto_industria": 8,     # Industria = industria de query
    "match_exacto_seniority": 8,     # Nivel = nivel solicitado (±1)
    "keyword_en_titulo": 10,         # Query aparece en current_title
    "trayectoria_consistente": 5,    # Carrera >80% en misma función
    "skills_match_alto": 4,          # 4+ skills coinciden
}


# ============= PENALTIES (NEGATIVOS) =============

PENALTIES = {
    # General Management en búsqueda funcional
    "gm_sin_evidencia": 25,          # GM sin trayectoria en área buscada
    "gm_evidencia_debil": 20,        # GM con mención superficial
    "gm_evidencia_moderada": 10,     # GM con algo de experiencia
    # GM con evidencia fuerte → 0 (no se penaliza)
    
    # Distancia de seniority
    "seniority_5_niveles": 15,       # 5+ niveles de diferencia
    "seniority_4_niveles": 8,        # 4 niveles de diferencia
    "seniority_3_niveles": 4,        # 3 niveles de diferencia
    
    # Función adyacente
    "funcion_adyacente": 8,          # Marketing↔Ventas, Ops↔SC
    
    # Industria
    "industria_no_transferible": 6,  # Industria muy diferente
    
    # Estabilidad laboral
    "estabilidad_high": 10,          # >1 empleo/año - AJUSTADO
    "estabilidad_moderate": 5,       # Rotación moderada
    "estabilidad_low": 2,            # Rotación leve
}


# ============= MULTIPLICADORES DE EXPERIENCIA FUNCIONAL =============

# Ajusta el score funcional según el nivel de experiencia en el área
MULTIPLICADORES_EXPERIENCIA = {
    "principal": 1.0,    # Carrera construida en esta función (≥60% trayectoria)
    "secundaria": 0.7,   # Experiencia significativa (30-60% trayectoria)
    "marginal": 0.4,     # Experiencia superficial (<30% trayectoria)
}


# ============= JERARQUÍA DE SENIORITY =============

SENIORITY_LEVELS = {
    "intern": 1,
    "entry": 1,
    "auxiliary": 2,
    "assistant": 2,
    "junior": 3,
    "analyst": 3,
    "coordinator": 4,
    "specialist": 4,
    "mid": 4,
    "supervisor": 5,
    "senior": 6,
    "lead": 6,
    "manager": 7,
    "senior_manager": 8,
    "director": 9,
    "vp": 10,
    "c_level": 11,
    "ceo": 12,
}

# Score por distancia de niveles
SENIORITY_DISTANCE_SCORES = {
    0: 100,   # Match exacto
    1: 90,    # ±1 nivel → muy aceptable
    2: 75,    # ±2 niveles → aceptable
    3: 50,    # ±3 niveles → cuestionable
    4: 25,    # ±4 niveles → poco relevante
    5: 10,    # ±5+ niveles → irrelevante
}


# ============= THRESHOLDS DE ESTABILIDAD =============

# Ratio de empleos por año
STABILITY_THRESHOLDS = {
    "very_stable": 0.25,    # ≤1 empleo cada 4 años
    "stable": 0.40,         # ≤1 empleo cada 2.5 años
    "moderate": 0.60,       # ≤1 empleo cada 1.7 años
    "concerning": 0.80,     # ≤1 empleo cada 1.25 años
    # >0.80 = high risk
}


# ============= AÑOS ESPERADOS POR NIVEL =============

EXPECTED_YEARS_BY_LEVEL = {
    1: (0, 1),    # Becario/Intern: 0-1 años
    2: (0, 2),    # Auxiliar/Assistant: 0-2 años
    3: (1, 4),    # Analista: 1-4 años
    4: (2, 6),    # Coordinador: 2-6 años
    5: (3, 8),    # Supervisor: 3-8 años
    6: (4, 10),   # Jefatura/Lead: 4-10 años
    7: (5, 15),   # Gerente/Manager: 5-15 años
    8: (8, 18),   # Sr. Manager: 8-18 años
    9: (10, 25),  # Director: 10-25 años
    10: (12, 30), # VP: 12-30 años
    11: (15, 35), # C-Level: 15-35 años
    12: (18, 40), # CEO/DG: 18-40 años
}
