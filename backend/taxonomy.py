"""
Taxonomía Maestra Bilingüe para Atlas Talent Vault

Este módulo define la taxonomía canónica de industrias y áreas funcionales.
Cada categoría tiene:
- key: Identificador único, estable, neutral al idioma
- name_es: Nombre en español (para UI)
- name_en: Nombre en inglés

La lógica de clasificación (Atlas AI) debe mapear términos en cualquier idioma
a estas keys canónicas.
"""

# Industrias
INDUSTRIES = [
    {"key": "manufacturing", "name_es": "Manufactura", "name_en": "Manufacturing"},
    {"key": "consumer_goods", "name_es": "Bienes de Consumo", "name_en": "Consumer Goods"},
    {"key": "retail", "name_es": "Retail", "name_en": "Retail"},
    {"key": "logistics_supply_chain", "name_es": "Logística y Cadena de Suministro", "name_en": "Logistics and Supply Chain"},
    {"key": "transportation", "name_es": "Transporte", "name_en": "Transportation"},
    {"key": "pharmaceutical", "name_es": "Farmacéutica", "name_en": "Pharmaceutical"},
    {"key": "construction", "name_es": "Construcción", "name_en": "Construction"},
    {"key": "real_estate", "name_es": "Bienes Raíces", "name_en": "Real Estate"},
    {"key": "financial_services", "name_es": "Servicios Financieros", "name_en": "Financial Services"},
    {"key": "technology", "name_es": "Tecnología", "name_en": "Technology"},
    {"key": "hospitality", "name_es": "Hospitalidad", "name_en": "Hospitality"},
    {"key": "industrial_services", "name_es": "Servicios Industriales", "name_en": "Industrial Services"},
    {"key": "energy", "name_es": "Energía", "name_en": "Energy"},
    {"key": "automotive", "name_es": "Automotriz", "name_en": "Automotive"},
    {"key": "food_beverage", "name_es": "Alimentos y Bebidas", "name_en": "Food and Beverage"},
    {"key": "professional_services", "name_es": "Servicios Profesionales", "name_en": "Professional Services"},
    {"key": "healthcare", "name_es": "Salud", "name_en": "Healthcare"},
    {"key": "agriculture", "name_es": "Agricultura", "name_en": "Agriculture"},
    {"key": "mining", "name_es": "Minería", "name_en": "Mining"},
    {"key": "telecommunications", "name_es": "Telecomunicaciones", "name_en": "Telecommunications"},
    {"key": "media_entertainment", "name_es": "Medios y Entretenimiento", "name_en": "Media and Entertainment"},
    {"key": "education", "name_es": "Educación", "name_en": "Education"},
]

# Áreas Funcionales
FUNCTIONAL_AREAS = [
    {"key": "general_management", "name_es": "Dirección General", "name_en": "General Management"},
    {"key": "operations", "name_es": "Operaciones", "name_en": "Operations"},
    {"key": "manufacturing", "name_es": "Manufactura", "name_en": "Manufacturing"},
    {"key": "supply_chain", "name_es": "Cadena de Suministro", "name_en": "Supply Chain"},
    {"key": "logistics", "name_es": "Logística", "name_en": "Logistics"},
    {"key": "procurement", "name_es": "Compras", "name_en": "Procurement"},
    {"key": "sales", "name_es": "Ventas", "name_en": "Sales"},
    {"key": "business_development", "name_es": "Desarrollo de Negocio", "name_en": "Business Development"},
    {"key": "marketing", "name_es": "Marketing", "name_en": "Marketing"},
    {"key": "finance", "name_es": "Finanzas", "name_en": "Finance"},
    {"key": "accounting", "name_es": "Contabilidad", "name_en": "Accounting"},
    {"key": "human_resources", "name_es": "Recursos Humanos", "name_en": "Human Resources"},
    {"key": "talent_acquisition", "name_es": "Adquisición de Talento", "name_en": "Talent Acquisition"},
    {"key": "engineering", "name_es": "Ingeniería", "name_en": "Engineering"},
    {"key": "quality", "name_es": "Calidad", "name_en": "Quality"},
    {"key": "maintenance", "name_es": "Mantenimiento", "name_en": "Maintenance"},
    {"key": "it", "name_es": "Tecnología de la Información", "name_en": "IT"},
    {"key": "legal", "name_es": "Legal", "name_en": "Legal"},
    {"key": "customer_service", "name_es": "Servicio al Cliente", "name_en": "Customer Service"},
    {"key": "project_management", "name_es": "Gestión de Proyectos", "name_en": "Project Management"},
    {"key": "construction_management", "name_es": "Gestión de Construcción", "name_en": "Construction Management"},
    {"key": "research_development", "name_es": "Investigación y Desarrollo", "name_en": "Research and Development"},
    {"key": "ehs", "name_es": "Seguridad, Higiene y Medio Ambiente", "name_en": "Environment, Health and Safety"},
    {"key": "planning", "name_es": "Planeación", "name_en": "Planning"},
]


def get_industry_by_key(key: str) -> dict:
    """Obtiene una industria por su key canónica"""
    for industry in INDUSTRIES:
        if industry["key"] == key:
            return industry
    return None


def get_functional_area_by_key(key: str) -> dict:
    """Obtiene un área funcional por su key canónica"""
    for area in FUNCTIONAL_AREAS:
        if area["key"] == key:
            return area
    return None


def get_industry_display_name(key: str, lang: str = "es") -> str:
    """Obtiene el nombre de una industria para mostrar en UI"""
    industry = get_industry_by_key(key)
    if industry:
        return industry.get(f"name_{lang}", industry["name_es"])
    return key


def get_functional_area_display_name(key: str, lang: str = "es") -> str:
    """Obtiene el nombre de un área funcional para mostrar en UI"""
    area = get_functional_area_by_key(key)
    if area:
        return area.get(f"name_{lang}", area["name_es"])
    return key


def build_taxonomy_prompt_section() -> str:
    """
    Construye la sección del prompt que lista la taxonomía para el LLM.
    El LLM debe usar las keys canónicas en sus respuestas.
    """
    industries_text = "\n".join([
        f"  - key: \"{i['key']}\" (ES: {i['name_es']} / EN: {i['name_en']})"
        for i in INDUSTRIES
    ])
    
    areas_text = "\n".join([
        f"  - key: \"{a['key']}\" (ES: {a['name_es']} / EN: {a['name_en']})"
        for a in FUNCTIONAL_AREAS
    ])
    
    return f"""
TAXONOMÍA DE INDUSTRIAS (responde SOLO con el 'key'):
{industries_text}

TAXONOMÍA DE ÁREAS FUNCIONALES (responde SOLO con el 'key'):
{areas_text}
"""


def get_all_industries() -> list:
    """Retorna todas las industrias"""
    return INDUSTRIES.copy()


def get_all_functional_areas() -> list:
    """Retorna todas las áreas funcionales"""
    return FUNCTIONAL_AREAS.copy()
