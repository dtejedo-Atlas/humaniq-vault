import os
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json
import re
from taxonomy import build_taxonomy_prompt_section, get_industry_by_key, get_functional_area_by_key

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Límite de caracteres para CVs (Claude Sonnet 4.5 soporta 200k tokens de contexto)
CV_MAX_CHARS = 20000


def smart_truncate_cv(text: str, max_chars: int = CV_MAX_CHARS) -> str:
    """
    Trunca inteligentemente un CV priorizando experiencia laboral y educación.
    
    Si el texto supera max_chars:
    1. Mantiene secciones de experiencia laboral y educación
    2. Recorta secciones de relleno (referencias, hobbies, cursos menores)
    3. Solo como último recurso corta contenido importante
    
    Args:
        text: Texto completo del CV
        max_chars: Límite máximo de caracteres
        
    Returns:
        Texto truncado inteligentemente
    """
    if len(text) <= max_chars:
        return text
    
    # Patrones para identificar secciones (case-insensitive, español e inglés)
    section_patterns = {
        'priority_high': [
            # Experiencia laboral - MÁXIMA PRIORIDAD
            r'(?:experiencia\s*(?:laboral|profesional)|work\s*experience|professional\s*experience|employment\s*history|historial\s*laboral|trayectoria\s*profesional)',
            # Educación - ALTA PRIORIDAD
            r'(?:educación|education|formación\s*académica|academic\s*background|estudios)',
            # Datos personales/contacto - ALTA PRIORIDAD (inicio del CV)
            r'(?:datos\s*personales|personal\s*info|contact|contacto)',
            # Resumen/Perfil - ALTA PRIORIDAD
            r'(?:resumen|summary|perfil\s*profesional|professional\s*profile|objetivo|objective)',
        ],
        'priority_medium': [
            # Skills/Competencias
            r'(?:habilidades|skills|competencias|competencies|conocimientos|aptitudes)',
            # Certificaciones
            r'(?:certificaciones|certifications|licencias|licenses)',
            # Idiomas
            r'(?:idiomas|languages)',
            # Logros
            r'(?:logros|achievements|accomplishments)',
        ],
        'priority_low': [
            # Cursos/Talleres
            r'(?:cursos|courses|talleres|workshops|capacitación|training)',
            # Referencias
            r'(?:referencias|references)',
            # Hobbies/Intereses
            r'(?:hobbies|intereses|interests|actividades|activities)',
            # Información adicional
            r'(?:información\s*adicional|additional\s*info|otros|other)',
            # Voluntariado
            r'(?:voluntariado|volunteer|servicio\s*social)',
        ]
    }
    
    lines = text.split('\n')
    sections = []
    current_section = {'priority': 'high', 'lines': [], 'name': 'header'}
    
    # Clasificar líneas por sección
    for line in lines:
        line_lower = line.lower().strip()
        
        # Detectar inicio de nueva sección
        section_found = False
        for priority, patterns in section_patterns.items():
            for pattern in patterns:
                if re.search(pattern, line_lower):
                    # Guardar sección anterior
                    if current_section['lines']:
                        sections.append(current_section)
                    # Iniciar nueva sección
                    current_section = {
                        'priority': priority.replace('priority_', ''),
                        'lines': [line],
                        'name': line_lower[:50]
                    }
                    section_found = True
                    break
            if section_found:
                break
        
        if not section_found:
            current_section['lines'].append(line)
    
    # Agregar última sección
    if current_section['lines']:
        sections.append(current_section)
    
    # Si no se detectaron secciones, truncar simple
    if len(sections) <= 1:
        return text[:max_chars]
    
    # Reconstruir priorizando secciones importantes
    result_lines = []
    current_length = 0
    
    # Primero agregar secciones de alta prioridad
    for section in sections:
        if section['priority'] == 'high':
            section_text = '\n'.join(section['lines'])
            if current_length + len(section_text) <= max_chars:
                result_lines.extend(section['lines'])
                current_length += len(section_text) + 1
    
    # Luego secciones de prioridad media
    for section in sections:
        if section['priority'] == 'medium':
            section_text = '\n'.join(section['lines'])
            if current_length + len(section_text) <= max_chars:
                result_lines.extend(section['lines'])
                current_length += len(section_text) + 1
    
    # Finalmente secciones de baja prioridad si hay espacio
    for section in sections:
        if section['priority'] == 'low':
            section_text = '\n'.join(section['lines'])
            if current_length + len(section_text) <= max_chars:
                result_lines.extend(section['lines'])
                current_length += len(section_text) + 1
    
    # Si aún tenemos espacio y faltan líneas, agregar lo que se pueda
    result_text = '\n'.join(result_lines)
    
    # Si el resultado está vacío o muy corto, hacer truncamiento simple
    if len(result_text) < max_chars * 0.3:
        return text[:max_chars]
    
    return result_text[:max_chars]

class AtlasAIService:
    def __init__(self):
        self.api_key = EMERGENT_LLM_KEY
    
    async def parse_resume(self, resume_text: str) -> dict:
        """Extract structured data from resume text using intelligent truncation"""
        
        # Aplicar truncamiento inteligente si el CV es muy largo
        # Claude Sonnet 4.5 soporta 200k tokens, pero limitamos a 20k chars para eficiencia
        processed_text = smart_truncate_cv(resume_text, CV_MAX_CHARS)
        
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"parse-{id(resume_text)}",
            system_message="""Eres Atlas, un experto en análisis de currículums para reclutamiento ejecutivo en México y Latinoamérica.
            
Tu tarea es extraer información estructurada de currículums. Debes ser preciso y profesional.
            
Siempre responde en formato JSON válido con esta estructura:
            {
                "full_name": "nombre completo",
                "email": "email o null",
                "phone": "teléfono o null",
                "city": "ciudad o null",
                "state": "estado o null",
                "country": "país (default México)",
                "linkedin_url": "URL de LinkedIn o null",
                "current_company": "empresa actual o null",
                "current_title": "puesto actual o null",
                "years_experience": "años de experiencia total como número o null",
                "skills": ["lista de habilidades clave"],
                "languages": ["lista de idiomas"],
                "previous_companies": [
                    {
                        "company_name": "nombre empresa",
                        "title": "puesto",
                        "start_date": "fecha inicio o null",
                        "end_date": "fecha fin o null",
                        "description": "descripción breve o null",
                        "company_caliber": "calibre de la empresa o null"
                    }
                ]
            }

Para "company_caliber", clasifica el calibre de cada empresa en UNO de estos 5 valores exactos:
- "multinacional_global": presencia en múltiples países, marca global reconocida
- "corporativo_nacional": gran empresa nacional o filial grande
- "mediana": empresa mediana establecida
- "pyme": pequeña o mediana empresa local
- "startup": empresa joven / emprendimiento
Si no hay información suficiente para clasificar una empresa, deja company_caliber en null. NO inventes.
            """
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(
            text=f"""Analiza el siguiente currículum y extrae toda la información estructurada.
            
Responde SOLO con JSON válido, sin texto adicional:
            
{processed_text}
            """
        )
        
        response = await chat.send_message(message)
        
        try:
            # Clean response and parse JSON
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            parsed_data = json.loads(response_text.strip())
            return parsed_data
        except json.JSONDecodeError:
            return {
                "full_name": "Desconocido",
                "error": "No se pudo parsear la respuesta"
            }
    
    async def classify_candidate(self, candidate_data: dict, resume_text: str) -> dict:
        """Classify candidate by industry, functional area, and seniority using bilingual taxonomy"""
        
        # Obtener la sección de taxonomía bilingüe para el prompt
        taxonomy_section = build_taxonomy_prompt_section()
        
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"classify-{id(candidate_data)}",
            system_message=f"""Eres Atlas, un experto en clasificación de perfiles profesionales para reclutamiento ejecutivo en México y Latinoamérica.

Tu tarea es clasificar candidatos por:
- Industria (industry)
- Área funcional / expertise (functional_area)
- Nivel de seniority

IMPORTANTE: 
1. El CV puede estar en español O inglés. Debes clasificar correctamente independientemente del idioma.
2. Debes responder usando ÚNICAMENTE las 'key' canónicas de la taxonomía, NO los nombres en español o inglés.
3. Por ejemplo, si el CV menciona "Supply Chain" o "Cadena de Suministro", responde con la key "supply_chain".

{taxonomy_section}

Niveles de seniority (usar estos valores exactos):
  - entry, junior, mid, senior, lead, manager, director, vp, c_level

Responde SOLO en formato JSON:
{{
    "industry": "key_de_industria",
    "functional_area": "key_de_area_funcional",
    "seniority": "nivel_de_seniority",
    "confidence_score": 0.85,
    "suggested_tags": ["tag1", "tag2", "tag3"],
    "reasoning": "breve explicación de la clasificación"
}}
"""
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(
            text=f"""Clasifica el siguiente perfil profesional:

Nombre: {candidate_data.get('full_name', 'N/A')}
Puesto actual: {candidate_data.get('current_title', 'N/A')}
Empresa actual: {candidate_data.get('current_company', 'N/A')}
Años de experiencia: {candidate_data.get('years_experience', 'N/A')}
Habilidades: {', '.join(candidate_data.get('skills', []))}

Texto del CV (primeros 3000 caracteres):
{resume_text[:3000]}

RECUERDA: Responde usando las 'key' canónicas de la taxonomía (ej: "manufacturing", "supply_chain"), NO los nombres en español o inglés.
Responde SOLO con JSON válido.
"""
        )
        
        response = await chat.send_message(message)
        
        try:
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            classification = json.loads(response_text.strip())
            
            # Validar que las keys existan en la taxonomía
            industry_key = classification.get('industry')
            functional_area_key = classification.get('functional_area')
            
            if industry_key and not get_industry_by_key(industry_key):
                # Intentar mapear si el LLM respondió con nombre en lugar de key
                classification['industry'] = self._normalize_to_key(industry_key, 'industry')
            
            if functional_area_key and not get_functional_area_by_key(functional_area_key):
                classification['functional_area'] = self._normalize_to_key(functional_area_key, 'functional_area')
            
            # Si tras normalizar algún valor sigue fuera del catálogo, penalizar confidence
            # para que el candidato caiga a la bandeja de revisión individual
            final_ind = classification.get('industry')
            final_area = classification.get('functional_area')
            if (final_ind and not get_industry_by_key(final_ind)) or \
               (final_area and not get_functional_area_by_key(final_area)):
                original_conf = classification.get('confidence_score', 0.0)
                classification['confidence_score'] = min(original_conf, 0.5)
                classification['reasoning'] = (classification.get('reasoning') or '') + \
                    ' [Confidence penalizada: valor de taxonomía fuera del catálogo canónico]'
            
            return classification
        except json.JSONDecodeError:
            return {
                "industry": None,
                "functional_area": None,
                "seniority": None,
                "confidence_score": 0.0,
                "suggested_tags": [],
                "reasoning": "Error en clasificación"
            }
    
    def _normalize_to_key(self, value: str, category_type: str) -> str:
        """Intenta normalizar un valor a su key canónica si el LLM respondió con nombre"""
        from taxonomy import INDUSTRIES, FUNCTIONAL_AREAS
        
        value_lower = value.lower().strip()
        
        if category_type == 'industry':
            for item in INDUSTRIES:
                if (value_lower == item['key'] or 
                    value_lower.replace(' ', '_') == item['key'] or
                    value_lower == item['name_es'].lower() or 
                    value_lower == item['name_en'].lower()):
                    return item['key']
        else:
            for item in FUNCTIONAL_AREAS:
                if (value_lower == item['key'] or 
                    value_lower.replace(' ', '_') == item['key'] or
                    value_lower == item['name_es'].lower() or 
                    value_lower == item['name_en'].lower()):
                    return item['key']
        
        # Si no se encuentra, devolver el valor original (puede ser categoría nueva)
        return value
    
    async def generate_summary(self, candidate_data: dict, resume_text: str) -> str:
        """Generate a professional candidate summary"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"summary-{id(candidate_data)}",
            system_message="Eres Atlas, un experto en redactar resúmenes profesionales de candidatos para reclutamiento ejecutivo. Genera resúmenes concisos, profesionales y en español que destaquen las fortalezas clave del candidato en 3-4 oraciones."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(
            text=f"""Genera un resumen profesional ejecutivo del siguiente candidato:
            
Nombre: {candidate_data.get('full_name', 'N/A')}
Puesto: {candidate_data.get('current_title', 'N/A')}
Empresa: {candidate_data.get('current_company', 'N/A')}
Experiencia: {candidate_data.get('years_experience', 'N/A')} años
Industria: {candidate_data.get('industry', 'N/A')}
Área: {candidate_data.get('functional_area', 'N/A')}
            
Texto del CV:
{resume_text[:4000]}
            
Resumen profesional (3-4 oraciones):
            """
        )
        
        response = await chat.send_message(message)
        return response.strip()
    
    async def match_candidate_to_job(self, candidate_data: dict, job_description: str) -> dict:
        """Match candidate against job profile and provide scoring"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"match-{id(candidate_data)}",
            system_message="""Eres Atlas, un experto en matching de candidatos para posiciones ejecutivas.
            
Analiza la compatibilidad entre un candidato y una vacante. Proporciona:
- Match score (0-100)
- Razones por las que es buen match
- Brechas o áreas de desarrollo
- Experiencia transferible
            
Responde en JSON:
{
    "match_score": 85,
    "reasons": ["razón 1", "razón 2"],
    "gaps": ["brecha 1", "brecha 2"],
    "transferable_experience": ["experiencia 1"],
    "recommendation": "recomendación final"
}
            """
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        candidate_summary = f"""
Candidato: {candidate_data.get('full_name', 'N/A')}
Puesto actual: {candidate_data.get('current_title', 'N/A')}
Empresa: {candidate_data.get('current_company', 'N/A')}
Experiencia: {candidate_data.get('years_experience', 'N/A')} años
Industria: {candidate_data.get('industry', 'N/A')}
Área: {candidate_data.get('functional_area', 'N/A')}
Seniority: {candidate_data.get('seniority', 'N/A')}
Habilidades: {', '.join(candidate_data.get('skills', []))}
        """
        
        message = UserMessage(
            text=f"""Analiza la compatibilidad entre este candidato y la vacante:
            
PERFIL DEL CANDIDATO:
{candidate_summary}
            
DESCRIPCIÓN DE LA VACANTE:
{job_description[:4000]}
            
Responde SOLO con JSON válido.
            """
        )
        
        response = await chat.send_message(message)
        
        try:
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            match_result = json.loads(response_text.strip())
            return match_result
        except json.JSONDecodeError:
            return {
                "match_score": 0,
                "reasons": [],
                "gaps": ["Error en análisis"],
                "transferable_experience": [],
                "recommendation": "No se pudo analizar"
            }

    async def parse_job_description(self, jd_text: str) -> dict:
        """
        Parse a Job Description document and extract structured data.
        
        This is designed to extract information from various JD formats:
        - Formal corporate JDs
        - Informal role descriptions
        - Recruitment agency briefs
        - LinkedIn-style postings
        
        Args:
            jd_text: Raw text extracted from PDF/DOCX
            
        Returns:
            dict with structured job data matching the Job model
        """
        taxonomy_section = build_taxonomy_prompt_section()
        
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"parse-jd-{id(jd_text)}",
            system_message=f"""Eres Humaniq AI, un experto en análisis de descripciones de puestos (Job Descriptions) para reclutamiento ejecutivo en México y Latinoamérica.

Tu tarea es extraer y estructurar información de descripciones de vacantes. Los documentos pueden venir en varios formatos:
- JDs corporativas formales
- Briefs de agencias de reclutamiento
- Publicaciones estilo LinkedIn
- Descripciones informales

IMPORTANTE:
1. Extrae TODA la información disponible, incluso si está implícita
2. Si algún campo no está claro, usa tu mejor juicio basado en el contexto
3. Para industria y área funcional, DEBES usar las keys canónicas de la taxonomía
4. Si el salario aparece en USD, conviértelo a MXN (usa 17.5 como tipo de cambio aproximado)
5. Si la ubicación no está clara pero hay pistas (nombre de empresa conocida, contexto), infiere lo más probable

{taxonomy_section}

NIVELES DE SENIORITY (usar estos valores exactos):
- trainee: Becario / Trainee (0-1 años)
- entry: Entry Level (0-2 años)
- junior: Junior / Coordinador (1-4 años)
- mid: Mid Level / Especialista (3-7 años)
- senior: Senior (5-12 años)
- lead: Lead / Líder (7-15 años)
- manager: Gerente / Manager (8-20 años)
- director: Director (10-25 años)
- vp: VP / Vicepresidente (12-30 años)
- c_level: C-Level (15+ años)

ESQUEMAS DE TRABAJO:
- on_site: Presencial
- hybrid: Híbrido
- remote: Remoto

Responde ÚNICAMENTE con JSON válido, sin texto adicional:
{{
    "title": "Título del puesto (limpio, sin empresa)",
    "company": "Nombre de la empresa o null si no se menciona",
    "industry": "key_canonica_de_industria",
    "functional_area": "key_canonica_de_area_funcional",
    "seniority": "nivel_seniority",
    "min_experience": numero_años_minimos,
    "max_experience": numero_años_maximos_o_null,
    "job_objective": "Objetivo principal del puesto (1-2 párrafos)",
    "role_context": "Contexto de la empresa, equipo o situación del rol",
    "responsibilities": "Responsabilidades principales (formato bullet points con •)",
    "required_experience": "Experiencia profesional requerida (descripción)",
    "non_negotiables": "Requisitos indispensables / no negociables (formato bullet points con •)",
    "location_country": "País (default México)",
    "location_state": "Estado/Región o null",
    "location_city": "Ciudad o null",
    "salary_min": numero_salario_minimo_mensual_MXN_o_null,
    "salary_max": numero_salario_maximo_mensual_MXN_o_null,
    "work_scheme": "on_site|hybrid|remote",
    "schedule": "Horario/jornada o null",
    "confidence_score": 0.0_a_1.0,
    "extraction_notes": "Notas sobre la extracción, campos inferidos o dudas"
}}
"""
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(
            text=f"""Analiza la siguiente descripción de vacante y extrae toda la información estructurada.

DOCUMENTO DE VACANTE:
{jd_text[:12000]}

Responde SOLO con JSON válido.
"""
        )
        
        response = await chat.send_message(message)
        
        try:
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            parsed_data = json.loads(response_text.strip())
            
            # Validar y normalizar campos críticos
            # Industria
            industry_key = parsed_data.get('industry')
            if industry_key and not get_industry_by_key(industry_key):
                parsed_data['industry'] = self._normalize_to_key_with_default(industry_key, 'industry')
            
            # Área funcional
            functional_area_key = parsed_data.get('functional_area')
            if functional_area_key and not get_functional_area_by_key(functional_area_key):
                parsed_data['functional_area'] = self._normalize_to_key_with_default(functional_area_key, 'functional_area')
            
            # Asegurar que los números sean números
            for field in ['min_experience', 'max_experience', 'salary_min', 'salary_max']:
                if parsed_data.get(field) is not None:
                    try:
                        parsed_data[field] = int(parsed_data[field]) if parsed_data[field] else None
                    except (ValueError, TypeError):
                        parsed_data[field] = None
            
            # Defaults
            if not parsed_data.get('location_country'):
                parsed_data['location_country'] = 'México'
            if not parsed_data.get('work_scheme'):
                parsed_data['work_scheme'] = 'on_site'
            if not parsed_data.get('seniority'):
                parsed_data['seniority'] = 'manager'
            if parsed_data.get('min_experience') is None:
                parsed_data['min_experience'] = 0
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            return {
                "error": f"Error parseando respuesta de AI: {str(e)}",
                "raw_response": response[:500] if response else None,
                "title": "Vacante sin título",
                "industry": "professional_services",
                "functional_area": "general_management",
                "seniority": "manager",
                "min_experience": 0,
                "location_country": "México",
                "work_scheme": "on_site",
                "confidence_score": 0.0,
                "extraction_notes": "Error en parsing. Revise el documento manualmente."
            }

    def _normalize_to_key_with_default(self, value: str, taxonomy_type: str) -> str:
        """
        Normalize a taxonomy value to its canonical key (flujo de vacantes).
        Falls back to a default if not found.
        """
        from taxonomy import get_all_industries, get_all_functional_areas
        
        value_lower = (value or "").lower().strip().replace(" ", "_").replace("-", "_")
        
        if taxonomy_type == 'industry':
            industries = get_all_industries()
            # Try exact match
            for ind in industries:
                if ind['key'] == value_lower:
                    return ind['key']
                if value_lower in ind['name_es'].lower() or value_lower in ind['name_en'].lower():
                    return ind['key']
            # Default
            return 'professional_services'
        
        elif taxonomy_type == 'functional_area':
            areas = get_all_functional_areas()
            # Try exact match
            for area in areas:
                if area['key'] == value_lower:
                    return area['key']
                if value_lower in area['name_es'].lower() or value_lower in area['name_en'].lower():
                    return area['key']
            # Default
            return 'general_management'
        
        return value


def classify_seniority(title: str, years_experience: float) -> dict:
    """
    Clasifica el seniority basándose en título del puesto y años de experiencia.
    
    Lógica transparente:
    1. Primero busca keywords en el título del puesto
    2. Si encuentra match, valida contra años de experiencia
    3. Si hay conflicto, prioriza años de experiencia (más objetivo)
    4. Retorna el seniority con explicación
    
    Args:
        title: Título del puesto más reciente
        years_experience: Años de experiencia total
    
    Returns:
        dict con 'seniority', 'confidence', 'reason'
    """
    from models import SENIORITY_TITLE_KEYWORDS, SENIORITY_LEVELS
    
    title_lower = (title or "").lower().strip()
    years = float(years_experience) if years_experience else 0
    
    # Paso 1: Detectar seniority por título
    title_seniority = None
    title_match_keyword = None
    
    # Buscar de más senior a menos senior para dar prioridad a títulos altos
    search_order = ["c_level", "vp", "director", "manager", "lead", "senior", "mid", "junior", "entry", "trainee"]
    
    import re
    for level in search_order:
        keywords = SENIORITY_TITLE_KEYWORDS.get(level, [])
        for kw in keywords:
            # Buscar palabra completa o al inicio/fin de palabra compuesta
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, title_lower):
                title_seniority = level
                title_match_keyword = kw
                break
        if title_seniority:
            break
    
    # Paso 2: Determinar seniority por años de experiencia
    years_seniority = None
    for level, config in SENIORITY_LEVELS.items():
        if config["years_min"] <= years <= config["years_max"]:
            years_seniority = level
            break
    
    # Si años exceden el máximo de c_level, asignar c_level
    if not years_seniority and years > 40:
        years_seniority = "c_level"
    elif not years_seniority:
        years_seniority = "entry"  # Default para casos extraños
    
    # Paso 3: Resolver conflictos
    final_seniority = None
    confidence = "high"
    reason = ""
    
    if title_seniority and years_seniority:
        title_level = SENIORITY_LEVELS.get(title_seniority, {}).get("level", 5)
        years_level = SENIORITY_LEVELS.get(years_seniority, {}).get("level", 5)
        
        # Si coinciden o están cerca (±1 nivel), usar título
        if abs(title_level - years_level) <= 1:
            final_seniority = title_seniority
            confidence = "high"
            reason = f"Título '{title_match_keyword}' coincide con {years} años de experiencia"
        # Si título indica más seniority que años, confiar en título (puede ser promoción rápida)
        elif title_level > years_level:
            final_seniority = title_seniority
            confidence = "medium"
            reason = f"Título '{title_match_keyword}' indica nivel alto para {years} años (posible fast-track)"
        # Si años indican más que título, usar años (título puede estar desactualizado)
        else:
            final_seniority = years_seniority
            confidence = "medium"
            reason = f"{years} años de experiencia sugieren nivel más alto que título actual"
    elif title_seniority:
        final_seniority = title_seniority
        confidence = "medium"
        reason = f"Basado en título '{title_match_keyword}' (sin años de experiencia)"
    elif years_seniority:
        final_seniority = years_seniority
        confidence = "medium"
        reason = f"Basado en {years} años de experiencia (título no determinante)"
    else:
        final_seniority = "mid"  # Default conservador
        confidence = "low"
        reason = "No se pudo determinar, asignado nivel medio por defecto"
    
    return {
        "seniority": final_seniority,
        "seniority_label": SENIORITY_LEVELS.get(final_seniority, {}).get("label", final_seniority),
        "confidence": confidence,
        "reason": reason,
        "title_detected": title_seniority,
        "years_detected": years_seniority,
        "input_title": title,
        "input_years": years
    }


atlas_service = AtlasAIService()