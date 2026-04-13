import os
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json
from taxonomy import build_taxonomy_prompt_section, get_industry_by_key, get_functional_area_by_key

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

class AtlasAIService:
    def __init__(self):
        self.api_key = EMERGENT_LLM_KEY
    
    async def parse_resume(self, resume_text: str) -> dict:
        """Extract structured data from resume text"""
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
                        "description": "descripción breve o null"
                    }
                ]
            }
            """
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(
            text=f"""Analiza el siguiente currículum y extrae toda la información estructurada.
            
Responde SOLO con JSON válido, sin texto adicional:
            
{resume_text[:8000]}
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
                    value_lower == item['name_es'].lower() or 
                    value_lower == item['name_en'].lower()):
                    return item['key']
        else:
            for item in FUNCTIONAL_AREAS:
                if (value_lower == item['key'] or 
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