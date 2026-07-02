"""
Affinity Matrices
=================
Matrices de afinidad para áreas funcionales e industrias.
Define qué tan transferible es la experiencia entre diferentes áreas/industrias.
"""

# ============= MATRIZ DE AFINIDAD FUNCIONAL =============
# Valor de 0-100 indicando qué tan relevante es un candidato de [fila] para una búsqueda de [columna]

FUNCTIONAL_AFFINITY = {
    # Candidato area →     HR    FIN   OPS   SC    MKT   SALES  IT    LEGAL  GM
    "human_resources":    {"human_resources": 100, "finance": 10,  "operations": 10,  "supply_chain": 10,  "marketing": 10,  "sales": 15,  "technology": 10,  "legal": 10,  "general_management": 25},
    "finance":            {"human_resources": 10,  "finance": 100, "operations": 15,  "supply_chain": 15,  "marketing": 10,  "sales": 20,  "technology": 10,  "legal": 25,  "general_management": 25},
    "operations":         {"human_resources": 10,  "finance": 15,  "operations": 100, "supply_chain": 70,  "marketing": 10,  "sales": 15,  "technology": 15,  "legal": 10,  "general_management": 35},
    "supply_chain":       {"human_resources": 10,  "finance": 10,  "operations": 70,  "supply_chain": 100, "marketing": 10,  "sales": 15,  "technology": 10,  "legal": 10,  "general_management": 30},
    "marketing":          {"human_resources": 15,  "finance": 10,  "operations": 10,  "supply_chain": 10,  "marketing": 100, "sales": 55,  "technology": 20,  "legal": 10,  "general_management": 20},
    "sales":              {"human_resources": 15,  "finance": 20,  "operations": 15,  "supply_chain": 15,  "marketing": 55,  "sales": 100, "technology": 15,  "legal": 10,  "general_management": 30},
    "technology":         {"human_resources": 10,  "finance": 15,  "operations": 20,  "supply_chain": 20,  "marketing": 20,  "sales": 15,  "technology": 100, "legal": 10,  "general_management": 20},
    "legal":              {"human_resources": 10,  "finance": 25,  "operations": 10,  "supply_chain": 10,  "marketing": 10,  "sales": 10,  "technology": 10,  "legal": 100, "general_management": 20},
    "general_management": {"human_resources": 25,  "finance": 25,  "operations": 35,  "supply_chain": 30,  "marketing": 20,  "sales": 30,  "technology": 20,  "legal": 20,  "general_management": 100},
}

# Áreas funcionales adyacentes (para penalty menor)
ADJACENT_FUNCTIONS = {
    ("marketing", "sales"),
    ("sales", "marketing"),
    ("operations", "supply_chain"),
    ("supply_chain", "operations"),
    ("finance", "legal"),
    ("legal", "finance"),
}


# ============= MATRIZ DE TRANSFERIBILIDAD INDUSTRIAL =============
# Valor de 0-100 indicando qué tan transferible es experiencia de [fila] a [columna]

INDUSTRY_TRANSFERABILITY = {
    # Candidato industria →          MANUF  RETAIL PHARMA FIN_SVC TECH   PROF_SVC CONSUMER ENERGY REAL_EST
    "manufacturing":                {"manufacturing": 100, "retail": 40,  "pharmaceutical": 50, "financial_services": 20, "technology": 30, "professional_services": 30, "consumer_goods": 45, "energy": 50, "real_estate": 20},
    "retail":                       {"manufacturing": 40,  "retail": 100, "pharmaceutical": 30, "financial_services": 35, "technology": 40, "professional_services": 50, "consumer_goods": 80, "energy": 20, "real_estate": 35},
    "pharmaceutical":               {"manufacturing": 50,  "retail": 30,  "pharmaceutical": 100, "financial_services": 30, "technology": 45, "professional_services": 40, "consumer_goods": 35, "energy": 30, "real_estate": 20},
    "financial_services":           {"manufacturing": 20,  "retail": 35,  "pharmaceutical": 30, "financial_services": 100, "technology": 50, "professional_services": 60, "consumer_goods": 30, "energy": 40, "real_estate": 55},
    "technology":                   {"manufacturing": 30,  "retail": 40,  "pharmaceutical": 45, "financial_services": 50, "technology": 100, "professional_services": 60, "consumer_goods": 45, "energy": 35, "real_estate": 30},
    "professional_services":        {"manufacturing": 30,  "retail": 50,  "pharmaceutical": 40, "financial_services": 60, "technology": 60, "professional_services": 100, "consumer_goods": 45, "energy": 40, "real_estate": 50},
    "consumer_goods":               {"manufacturing": 45,  "retail": 80,  "pharmaceutical": 35, "financial_services": 30, "technology": 45, "professional_services": 45, "consumer_goods": 100, "energy": 25, "real_estate": 30},
    "energy":                       {"manufacturing": 50,  "retail": 20,  "pharmaceutical": 30, "financial_services": 40, "technology": 35, "professional_services": 40, "consumer_goods": 25, "energy": 100, "real_estate": 35},
    "real_estate":                  {"manufacturing": 20,  "retail": 35,  "pharmaceutical": 20, "financial_services": 55, "technology": 30, "professional_services": 50, "consumer_goods": 30, "energy": 35, "real_estate": 100},
    "food_beverage":                {"manufacturing": 60,  "retail": 70,  "pharmaceutical": 40, "financial_services": 25, "technology": 30, "professional_services": 35, "consumer_goods": 85, "energy": 25, "real_estate": 25},
    "automotive":                   {"manufacturing": 80,  "retail": 45,  "pharmaceutical": 30, "financial_services": 30, "technology": 50, "professional_services": 35, "consumer_goods": 40, "energy": 45, "real_estate": 25},
    "healthcare":                   {"manufacturing": 40,  "retail": 35,  "pharmaceutical": 75, "financial_services": 35, "technology": 45, "professional_services": 50, "consumer_goods": 30, "energy": 25, "real_estate": 30},
    "logistics":                    {"manufacturing": 55,  "retail": 60,  "pharmaceutical": 40, "financial_services": 30, "technology": 40, "professional_services": 45, "consumer_goods": 55, "energy": 40, "real_estate": 35},
    "telecommunications":           {"manufacturing": 35,  "retail": 45,  "pharmaceutical": 30, "financial_services": 45, "technology": 70, "professional_services": 50, "consumer_goods": 40, "energy": 40, "real_estate": 30},
}


def get_functional_affinity(candidate_area: str, query_area: str) -> int:
    """
    Obtiene el score de afinidad funcional entre área del candidato y área de la query.
    
    Args:
        candidate_area: Área funcional del candidato
        query_area: Área funcional buscada en la query
        
    Returns:
        Score de 0-100
    """
    if not candidate_area or not query_area:
        return 50  # Valor neutral si falta información
    
    candidate_area = candidate_area.lower().strip()
    query_area = query_area.lower().strip()
    
    # FIX: commercial es sinónimo de sales
    if candidate_area == "commercial":
        candidate_area = "sales"
    if query_area == "commercial":
        query_area = "sales"
    
    if candidate_area in FUNCTIONAL_AFFINITY:
        return FUNCTIONAL_AFFINITY[candidate_area].get(query_area, 30)
    
    # Si el área no está en la matriz, retornar valor bajo
    return 20


def get_industry_transferability(candidate_industry: str, query_industry: str) -> int:
    """
    Obtiene el score de transferibilidad industrial.
    
    Args:
        candidate_industry: Industria del candidato
        query_industry: Industria buscada en la query
        
    Returns:
        Score de 0-100
    """
    if not candidate_industry or not query_industry:
        return 60  # Valor moderado si falta información
    
    candidate_industry = candidate_industry.lower().strip()
    query_industry = query_industry.lower().strip()
    
    # Match exacto
    if candidate_industry == query_industry:
        return 100
    
    if candidate_industry in INDUSTRY_TRANSFERABILITY:
        return INDUSTRY_TRANSFERABILITY[candidate_industry].get(query_industry, 40)
    
    # Si la industria no está en la matriz, retornar valor medio-bajo
    return 35


def are_adjacent_functions(func1: str, func2: str) -> bool:
    """
    Verifica si dos funciones son adyacentes (relacionadas pero distintas).
    """
    if not func1 or not func2:
        return False
    
    func1 = func1.lower().strip()
    func2 = func2.lower().strip()
    
    return (func1, func2) in ADJACENT_FUNCTIONS or (func2, func1) in ADJACENT_FUNCTIONS
