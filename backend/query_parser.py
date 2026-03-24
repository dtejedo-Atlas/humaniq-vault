"""
Query Parser
============
Parsea queries de búsqueda para extraer área funcional, industria, seniority y keywords.
"""

import re
from typing import Optional, Dict, List, Any

# ============= KEYWORDS POR ÁREA FUNCIONAL =============

AREA_KEYWORDS = {
    "human_resources": [
        "hr", "rh", "recursos humanos", "human resources", "talento", "talent",
        "reclutamiento", "recruitment", "compensaciones", "nomina", "nómina",
        "capacitación", "training", "desarrollo organizacional", "people",
        "headhunter", "chro", "chief human resources"
    ],
    "finance": [
        "finance", "finanzas", "financiero", "cfo", "contabilidad", "accounting",
        "tesorería", "treasury", "controller", "contralor", "fiscal", "tax",
        "auditoría", "audit", "planning", "planeación financiera", "fp&a"
    ],
    "operations": [
        "operations", "operaciones", "coo", "producción", "production",
        "manufactura", "manufacturing", "planta", "plant", "lean",
        "mejora continua", "continuous improvement", "calidad", "quality"
    ],
    "supply_chain": [
        "supply chain", "cadena de suministro", "logística", "logistics",
        "compras", "procurement", "purchasing", "almacén", "warehouse",
        "distribución", "distribution", "inventario", "inventory", "s&op"
    ],
    "marketing": [
        "marketing", "mercadotecnia", "cmo", "brand", "marca", "digital",
        "comunicación", "communications", "publicidad", "advertising",
        "producto", "product", "growth", "content", "social media"
    ],
    "sales": [
        "sales", "ventas", "comercial", "business development", "cro",
        "account", "cliente", "customer", "revenue", "key account",
        "trade", "canal", "channel", "retail sales"
    ],
    "technology": [
        "technology", "tecnología", "cto", "cio", "it", "sistemas", "systems",
        "software", "desarrollo", "development", "data", "analytics",
        "infraestructura", "infrastructure", "devops", "engineering"
    ],
    "legal": [
        "legal", "jurídico", "abogado", "lawyer", "attorney", "compliance",
        "cumplimiento", "regulatorio", "regulatory", "contratos", "contracts",
        "corporativo", "corporate counsel"
    ],
    "general_management": [
        "ceo", "director general", "dg", "presidente", "president",
        "country manager", "general manager", "gerente general", "managing director",
        "md", "chief executive"
    ],
}


# ============= KEYWORDS POR SENIORITY =============

SENIORITY_KEYWORDS = {
    1: ["becario", "intern", "practicante", "trainee", "pasante"],
    2: ["auxiliar", "assistant", "asistente", "support", "apoyo"],
    3: ["analista", "analyst", "junior", "jr"],
    4: ["coordinador", "coordinator", "especialista", "specialist"],
    5: ["supervisor", "team lead", "líder de equipo"],
    6: ["jefe", "head", "lead", "jefatura", "encargado"],
    7: ["gerente", "manager", "mgr"],
    8: ["senior manager", "sr manager", "gerente senior", "sr. manager"],
    9: ["director", "dir"],
    10: ["vp", "vicepresidente", "vice president", "vice presidente"],
    11: ["cfo", "coo", "cmo", "cto", "cio", "chro", "cpo", "c-level", "chief"],
    12: ["ceo", "director general", "presidente", "president", "country manager", "managing director"],
}


# ============= KEYWORDS POR INDUSTRIA =============

INDUSTRY_KEYWORDS = {
    "manufacturing": ["manufactura", "manufacturing", "industrial", "fábrica", "factory", "producción"],
    "retail": ["retail", "minorista", "tienda", "store", "comercio", "punto de venta"],
    "pharmaceutical": ["farmacéutica", "pharmaceutical", "pharma", "medicamento", "laboratorio"],
    "financial_services": ["financiero", "financial", "banco", "bank", "seguros", "insurance", "fintech"],
    "technology": ["tecnología", "technology", "tech", "software", "saas", "startup"],
    "professional_services": ["consultoría", "consulting", "servicios profesionales", "advisory"],
    "consumer_goods": ["consumo", "consumer", "fmcg", "cpg", "bienes de consumo"],
    "energy": ["energía", "energy", "petróleo", "oil", "gas", "renovable", "renewable"],
    "real_estate": ["inmobiliario", "real estate", "bienes raíces", "construcción", "construction"],
    "food_beverage": ["alimentos", "food", "bebidas", "beverage", "f&b"],
    "automotive": ["automotriz", "automotive", "auto", "vehículos", "vehicles"],
    "healthcare": ["salud", "healthcare", "hospital", "clínica", "clinic", "medical"],
    "logistics": ["logística", "logistics", "transporte", "transportation", "freight", "courier"],
    "telecommunications": ["telecomunicaciones", "telecom", "telecommunications", "móvil", "mobile"],
}


def parse_query(query: str) -> Dict[str, Any]:
    """
    Parsea una query de búsqueda y extrae:
    - area_funcional: Área funcional detectada
    - industria: Industria detectada
    - seniority_index: Nivel de seniority detectado (1-12)
    - keywords: Lista de palabras clave relevantes
    - query_clean: Query limpia sin stopwords
    
    Args:
        query: Texto de búsqueda del usuario
        
    Returns:
        Dict con los componentes parseados
    """
    if not query:
        return {
            "area_funcional": None,
            "industria": None,
            "seniority_index": None,
            "keywords": [],
            "query_clean": "",
            "raw_query": ""
        }
    
    query_lower = query.lower().strip()
    
    # Detectar área funcional
    area_funcional = detect_functional_area(query_lower)
    
    # Detectar industria
    industria = detect_industry(query_lower)
    
    # Detectar seniority
    seniority_index = detect_seniority(query_lower)
    
    # Extraer keywords significativas
    keywords = extract_keywords(query_lower)
    
    # Limpiar query
    query_clean = clean_query(query_lower)
    
    return {
        "area_funcional": area_funcional,
        "industria": industria,
        "seniority_index": seniority_index,
        "keywords": keywords,
        "query_clean": query_clean,
        "raw_query": query
    }


def detect_functional_area(query: str) -> Optional[str]:
    """
    Detecta el área funcional mencionada en la query.
    Prioriza matches más específicos.
    """
    query = query.lower()
    
    # Buscar coincidencias
    matches = []
    for area, keywords in AREA_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query:
                # Priorizar keywords más largos (más específicos)
                matches.append((area, len(keyword), keyword))
    
    if not matches:
        return None
    
    # Ordenar por longitud de keyword (más específico primero)
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches[0][0]


def detect_industry(query: str) -> Optional[str]:
    """
    Detecta la industria mencionada en la query.
    """
    query = query.lower()
    
    matches = []
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query:
                matches.append((industry, len(keyword)))
    
    if not matches:
        return None
    
    # Ordenar por longitud de keyword
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches[0][0]


def detect_seniority(query: str) -> Optional[int]:
    """
    Detecta el nivel de seniority en la query.
    Retorna índice 1-12 o None si no se detecta.
    """
    query = query.lower()
    
    # Buscar desde niveles más altos (más específicos) hacia abajo
    for level in range(12, 0, -1):
        keywords = SENIORITY_KEYWORDS.get(level, [])
        for keyword in keywords:
            if keyword in query:
                return level
    
    return None


def extract_keywords(query: str) -> List[str]:
    """
    Extrae palabras clave significativas de la query.
    Elimina stopwords y palabras muy cortas.
    """
    STOPWORDS = {
        "de", "en", "con", "para", "por", "del", "la", "el", "los", "las",
        "un", "una", "y", "o", "a", "e", "que", "se", "es", "al", "como",
        "the", "in", "with", "for", "of", "and", "or", "to", "is", "at"
    }
    
    # Tokenizar
    words = re.findall(r'\b[a-záéíóúñü]+\b', query.lower())
    
    # Filtrar stopwords y palabras cortas
    keywords = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    
    return keywords


def clean_query(query: str) -> str:
    """
    Limpia la query eliminando stopwords y normalizando.
    """
    keywords = extract_keywords(query)
    return " ".join(keywords)


def infer_area_from_title(title: str) -> Optional[str]:
    """
    Infiere el área funcional a partir de un título de puesto.
    Útil para analizar historial de empresas.
    """
    if not title:
        return None
    
    title = title.lower()
    
    # Patrones específicos por área
    patterns = {
        "human_resources": [r"rh\b", r"hr\b", r"recursos humanos", r"talento", r"people"],
        "finance": [r"finanz", r"financ", r"contab", r"controller", r"tesor", r"fiscal"],
        "operations": [r"operacion", r"operation", r"producción", r"planta", r"manufactur"],
        "supply_chain": [r"supply chain", r"logíst", r"logist", r"compras", r"almacén", r"cadena"],
        "marketing": [r"marketing", r"mercadotecnia", r"brand", r"digital", r"comunicación"],
        "sales": [r"ventas", r"sales", r"comercial", r"account", r"business dev"],
        "technology": [r"tecnolog", r"systems", r"software", r"datos", r"data", r"it\b"],
        "legal": [r"legal", r"jurídic", r"abogad", r"compliance"],
        "general_management": [r"director general", r"ceo\b", r"presidente", r"country manager", r"gerente general"],
    }
    
    for area, area_patterns in patterns.items():
        for pattern in area_patterns:
            if re.search(pattern, title):
                return area
    
    return None


def infer_seniority_from_title(title: str) -> Optional[int]:
    """
    Infiere el nivel de seniority a partir de un título.
    """
    if not title:
        return None
    
    title = title.lower()
    
    # Patrones ordenados de más específico a menos
    patterns = [
        (12, [r"\bceo\b", r"director general", r"presidente", r"country manager"]),
        (11, [r"\bcfo\b", r"\bcoo\b", r"\bcmo\b", r"\bcto\b", r"\bcio\b", r"\bchro\b", r"chief"]),
        (10, [r"\bvp\b", r"vicepresidente", r"vice president"]),
        (9, [r"\bdirector\b", r"\bdir\b"]),
        (8, [r"senior manager", r"sr.? manager", r"gerente senior"]),
        (7, [r"\bgerente\b", r"\bmanager\b"]),
        (6, [r"\bjefe\b", r"\bhead\b", r"\blead\b"]),
        (5, [r"\bsupervisor\b"]),
        (4, [r"\bcoordinador\b", r"\bespecialista\b", r"\bcoordinator\b", r"\bspecialist\b"]),
        (3, [r"\banalista\b", r"\banalyst\b"]),
        (2, [r"\bauxiliar\b", r"\basistente\b", r"\bassistant\b"]),
        (1, [r"\bbecario\b", r"\bintern\b", r"\bpracticante\b"]),
    ]
    
    for level, level_patterns in patterns:
        for pattern in level_patterns:
            if re.search(pattern, title):
                return level
    
    return 7  # Default a nivel manager si no se puede inferir
