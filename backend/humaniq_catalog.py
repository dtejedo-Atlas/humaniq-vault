"""Capa de presentación Humaniq (15 áreas / 105 subáreas / 13 seniorities).

Traduce la taxonomía de presentación a las claves técnicas que el motor de
matching ya reconoce. NO modifica scoring, pesos ni matrices: sólo garantiza
que `functional_area` y `seniority` guardados sean claves que el motor conoce.
"""
import json
import unicodedata
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "catalogo_humaniq.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
AREAS = CATALOG["areas"]
SENIORITY_LEVELS = CATALOG["seniority_levels"]
CATALOG_VERSION = CATALOG["version"]

# Claves reconocidas por FUNCTIONAL_AFFINITY (affinity_matrices.py). Única fuente del motor.
ENGINE_AREAS = ("human_resources", "finance", "operations", "supply_chain", "marketing",
                "sales", "technology", "legal", "general_management")

# Áreas de presentación → clave del motor. None = sin equivalencia (revisión manual).
AREA_TO_ENGINE = {
    "finanzas": "finance",
    "ventas": "sales",
    "marketing": "marketing",
    "operaciones": "operations",
    "manufactura": "operations",
    "cadena_suministro": "supply_chain",
    "recursos_humanos": "human_resources",
    "tecnologia": "technology",
    "ingenieria": "operations",
    "legal": "legal",
    "administracion": "general_management",
    "servicio_cliente": "operations",
    "salud": None,
    "proyectos_construccion": "operations",
    "sustentabilidad": None,
}

# Seniority de presentación → clave del motor (SeniorityLevel + SENIORITY_TO_INDEX).
SENIORITY_TO_ENGINE = {
    "becario": "entry",
    "trainee": "trainee",
    "auxiliar": "junior",
    "analista": "mid",
    "coordinador": "senior",
    "jefatura": "lead",
    "gerencia_jr": "manager",
    "gerencia": "manager",
    "gerencia_sr": "manager",
    "subdireccion": "director",
    "direccion": "director",
    "vicepresidencia": "vp",
    "c_level": "c_level",
}

# Claves históricas de taxonomy.py / inglés → (área de presentación, subárea sugerida)
LEGACY_AREA_MAP = {
    "general_management": ("administracion", "direccion_general"),
    "operations": ("operaciones", None),
    "manufacturing": ("manufactura", "produccion"),
    "supply_chain": ("cadena_suministro", None),
    "logistics": ("cadena_suministro", "logistica"),
    "procurement": ("cadena_suministro", "compras"),
    "sales": ("ventas", None),
    "commercial": ("ventas", None),
    "business_development": ("ventas", "desarrollo_negocio"),
    "marketing": ("marketing", None),
    "finance": ("finanzas", None),
    "accounting": ("finanzas", "contabilidad"),
    "human_resources": ("recursos_humanos", None),
    "talent_acquisition": ("recursos_humanos", "atraccion_talento"),
    "engineering": ("ingenieria", None),
    "quality": ("manufactura", "calidad"),
    "maintenance": ("manufactura", "mantenimiento"),
    "it": ("tecnologia", None),
    "technology": ("tecnologia", None),
    "legal": ("legal", None),
    "customer_service": ("servicio_cliente", None),
    "project_management": ("operaciones", "gestion_proyectos_op"),
    "construction_management": ("proyectos_construccion", "direccion_obra"),
    "research_development": ("ingenieria", "diseno"),
    "ehs": ("manufactura", "seguridad_industrial"),
    "planning": ("operaciones", "planeacion_operaciones"),
}

# Sinónimos en lenguaje natural que el LLM puede devolver.
AREA_ALIASES = {
    "finanzas": ["finance", "financial", "finanzas y administracion", "contraloria", "accounting"],
    "ventas": ["sales", "comercial", "commercial", "ventas y marketing", "business development"],
    "marketing": ["mercadotecnia", "brand", "comunicacion"],
    "operaciones": ["operations", "operativo"],
    "manufactura": ["manufacturing", "produccion", "production", "planta", "plant", "operaciones industriales"],
    "cadena_suministro": ["supply chain", "logistica", "logistics", "compras", "procurement", "abastecimiento"],
    "recursos_humanos": ["human resources", "hr", "rrhh", "capital humano", "people", "talento"],
    "tecnologia": ["technology", "it", "ti", "it_technology", "information technology", "sistemas", "software", "datos", "data"],
    "ingenieria": ["engineering", "ingeniero", "engineer", "i+d", "research and development"],
    "legal": ["juridico", "compliance", "regulatorio", "abogado"],
    "administracion": ["general management", "direccion general", "administracion y finanzas", "ceo", "strategy",
                       "planeacion estrategica"],
    "servicio_cliente": ["customer service", "customer success", "atencion a clientes", "call center",
                         "customer experience", "cx"],
    "salud": ["healthcare", "health", "ciencias de la vida", "life sciences", "medico", "farmaceutico", "pharma"],
    "proyectos_construccion": ["construction", "construccion", "obra", "proyectos de construccion", "project management"],
    "sustentabilidad": ["sustainability", "esg", "medio ambiente", "environment", "responsabilidad social"],
}

SENIORITY_ALIASES = {
    "becario": ["intern", "internship", "practicante", "pasante", "aprendiz", "becaria", "practicas"],
    "trainee": ["entrenamiento", "programa de trainees"],
    "auxiliar": ["entry", "asistente", "assistant", "auxiliary", "recien egresado", "graduate"],
    "analista": ["analyst", "especialista", "specialist", "junior", "jr", "associate", "asociado"],
    "coordinador": ["coordinator", "coordinadora", "mid", "mid-level"],
    "jefatura": ["jefe", "jefa", "lead", "team lead", "head", "head of", "supervisor", "senior", "sr", "lider", "principal"],
    "gerencia_jr": ["gerente junior", "gerente jr", "junior manager"],
    "gerencia": ["gerente", "manager", "management"],
    "gerencia_sr": ["gerente senior", "senior manager", "senior_manager", "gerente sr"],
    "subdireccion": ["subdirector", "subdirectora", "deputy director", "assistant director"],
    "direccion": ["director", "directora", "direction", "regional director"],
    "vicepresidencia": ["vp", "vice president", "vicepresidente", "svp", "evp"],
    "c_level": ["ceo", "cfo", "coo", "cto", "cio", "cmo", "chro", "chief", "presidente", "president",
                "managing director", "director general", "country manager", "socio", "partner", "founder", "fundador"],
}


def _fold(value) -> str:
    """minúsculas, sin acentos, separadores normalizados."""
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value.strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    cleaned = "".join(char if char.isalnum() else "_" for char in text)
    return "_".join(part for part in cleaned.split("_") if part)


def _build_area_index():
    index = {}

    def add(token, area_key, subarea_key=None):
        folded = _fold(token)
        if folded and folded not in index:
            index[folded] = (area_key, subarea_key)

    # Precedencia: área > clave histórica > sinónimo > subárea.
    for area in AREAS:
        add(area["key"], area["key"])
        add(area["label"], area["key"])
        for piece in area["label"].split("/"):
            add(piece, area["key"])
    for legacy, (area_key, subarea_key) in LEGACY_AREA_MAP.items():
        add(legacy, area_key, subarea_key)
    for area_key, aliases in AREA_ALIASES.items():
        for alias in aliases:
            add(alias, area_key)
    for area in AREAS:
        for subarea in area["subareas"]:
            add(subarea["key"], area["key"], subarea["key"])
            add(subarea["label"], area["key"], subarea["key"])
            for piece in subarea["label"].replace("(", "/").replace(")", "/").split("/"):
                add(piece, area["key"], subarea["key"])
    return index


def _build_seniority_index():
    index = {}

    def add(token, key):
        folded = _fold(token)
        if folded and folded not in index:
            index[folded] = key

    for level in SENIORITY_LEVELS:
        add(level["key"], level["key"])
        for piece in level["label"].split("/"):
            add(piece, level["key"])
        add(level["label"], level["key"])
    for key, aliases in SENIORITY_ALIASES.items():
        for alias in aliases:
            add(alias, key)
    # Las claves del motor siempre deben resolverse a su nivel de presentación.
    for presentation, engine in SENIORITY_TO_ENGINE.items():
        add(engine, presentation)
    return index


def _build_subarea_index():
    """Índice exclusivo de subáreas: evita que un alias de área tape una subárea."""
    index = {}
    for area in AREAS:
        for subarea in area["subareas"]:
            tokens = [subarea["key"], subarea["label"]]
            tokens += subarea["label"].replace("(", "/").replace(")", "/").split("/")
            for token in tokens:
                folded = _fold(token)
                if folded and folded not in index:
                    index[folded] = (area["key"], subarea["key"])
    return index


AREA_INDEX = _build_area_index()
SUBAREA_INDEX = _build_subarea_index()
SENIORITY_INDEX = _build_seniority_index()
AREA_BY_KEY = {area["key"]: area for area in AREAS}
SENIORITY_BY_KEY = {level["key"]: level for level in SENIORITY_LEVELS}


def resolve_area(raw, raw_subarea=None):
    """Normaliza cualquier valor de área (ES/EN, key, label, subárea) antes de
    declararlo fuera de catálogo. Devuelve None sólo si no hay coincidencia."""
    match = AREA_INDEX.get(_fold(raw))
    if not match:
        return None
    area_key, subarea_key = match
    if raw_subarea:
        explicit = SUBAREA_INDEX.get(_fold(raw_subarea))
        if explicit and explicit[0] == area_key:
            subarea_key = explicit[1]
    return {
        "presentation_area": area_key,
        "presentation_subarea": subarea_key,
        "engine_area": AREA_TO_ENGINE[area_key],
    }


def resolve_seniority(raw):
    """Normaliza cualquier valor de seniority a la escala de presentación y del motor."""
    key = SENIORITY_INDEX.get(_fold(raw))
    if not key:
        return None
    return {"presentation_seniority": key, "engine_seniority": SENIORITY_TO_ENGINE[key]}


def normalize_classification(values: dict) -> dict:
    """Aplica la normalización a un dict de clasificación.

    Devuelve los campos técnicos (`functional_area`, `seniority`) siempre con
    claves del motor, más los campos de presentación y la lista de valores que
    quedaron realmente fuera de catálogo.
    """
    result = dict(values)
    out_of_catalog = []
    no_engine_equivalent = []

    area = resolve_area(values.get("functional_area"), values.get("presentation_subarea"))
    if values.get("functional_area"):
        if not area:
            # Nunca se guarda un valor que el motor no reconoce: cae a revisión manual.
            out_of_catalog.append(f"functional_area={values.get('functional_area')}")
            result["functional_area"] = None
        else:
            result["presentation_area"] = area["presentation_area"]
            result["presentation_subarea"] = area["presentation_subarea"]
            if area["engine_area"]:
                result["functional_area"] = area["engine_area"]
            else:
                result["functional_area"] = None
                no_engine_equivalent.append(area["presentation_area"])

    if values.get("seniority"):
        seniority = resolve_seniority(values.get("seniority"))
        if not seniority:
            out_of_catalog.append(f"seniority={values.get('seniority')}")
            result["seniority"] = None
        else:
            result["presentation_seniority"] = seniority["presentation_seniority"]
            result["seniority"] = seniority["engine_seniority"]

    result["taxonomy_version"] = CATALOG_VERSION
    if out_of_catalog:
        result["out_of_catalog"] = out_of_catalog
    if no_engine_equivalent:
        result["no_engine_equivalent"] = no_engine_equivalent
    return result


PRESENTATION_FIELDS = ("presentation_area", "presentation_subarea", "presentation_seniority", "taxonomy_version")


def presentation_fields(source: dict) -> dict:
    """Extrae los campos de presentación de un dict de clasificación."""
    source = source or {}
    return {field: source.get(field) for field in PRESENTATION_FIELDS}


ENGINE_AREA_LABELS = {
    "finance": "Finanzas",
    "sales": "Ventas / Comercial",
    "marketing": "Marketing",
    "operations": "Operaciones",
    "supply_chain": "Cadena de Suministro / Logística",
    "human_resources": "Recursos Humanos / Capital Humano",
    "technology": "Tecnología / TI",
    "legal": "Legal / Jurídico",
    "general_management": "Administración / Dirección General",
}


def normalize_job_taxonomy(values: dict) -> dict:
    """Vacantes: el área y el seniority se guardan con la clave del motor."""
    result = dict(values)
    raw_area = values.get("presentation_area") or values.get("functional_area")
    if raw_area:
        area = resolve_area(raw_area, values.get("presentation_subarea"))
        if area and area["engine_area"]:
            result["presentation_area"] = area["presentation_area"]
            result["presentation_subarea"] = area["presentation_subarea"]
            result["functional_area"] = area["engine_area"]
    raw_seniority = values.get("presentation_seniority") or values.get("seniority")
    if raw_seniority:
        seniority = resolve_seniority(raw_seniority)
        if seniority:
            result["presentation_seniority"] = seniority["presentation_seniority"]
            result["seniority"] = seniority["engine_seniority"]
    return result


def public_catalog() -> dict:
    """Catálogo para la UI (áreas con subáreas y seniorities ordenados)."""
    return {
        "version": CATALOG_VERSION,
        "areas": [
            {
                "key": area["key"],
                "label": area["label"],
                "engine_area": AREA_TO_ENGINE[area["key"]],
                "subareas": area["subareas"],
            }
            for area in AREAS
        ],
        "seniority_levels": [
            {**level, "engine_seniority": SENIORITY_TO_ENGINE[level["key"]]}
            for level in sorted(SENIORITY_LEVELS, key=lambda item: item["rank"])
        ],
    }


def build_humaniq_prompt_section() -> str:
    """Sección de prompt con el catálogo de presentación para el LLM."""
    lines = []
    for area in AREAS:
        subareas = ", ".join(f'"{sub["key"]}"' for sub in area["subareas"])
        lines.append(f'  - area "{area["key"]}" ({area["label"]}) → subáreas: {subareas}')
    seniorities = "\n".join(
        f'  - "{level["key"]}" ({level["label"]}, nivel {level["rank"]} de 13)'
        for level in sorted(SENIORITY_LEVELS, key=lambda item: item["rank"])
    )
    return f"""
CATÁLOGO DE ÁREAS FUNCIONALES HUMANIQ (responde con la 'key' del área y de la subárea):
{chr(10).join(lines)}

ESCALA DE SENIORITY HUMANIQ (responde con la 'key'):
{seniorities}

REGLAS:
- Responde SIEMPRE con las keys exactas de este catálogo, en español, nunca en inglés ni con el nombre largo.
- functional_area debe ser una de las 15 keys de área.
- presentation_subarea es OBLIGATORIA cuando functional_area no es null: elige la subárea de ESA área que mejor describa el trabajo real del candidato. Nunca la dejes en null si ya elegiste un área.
- No inventes keys. Si ninguna área encaja, deja functional_area y presentation_subarea en null en lugar de aproximar.
"""
