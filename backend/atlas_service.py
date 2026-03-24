import os
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json

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
        """Classify candidate by industry, functional area, and seniority"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"classify-{id(candidate_data)}",
            system_message="""Eres Atlas, un experto en clasificación de perfiles profesionales para reclutamiento ejecutivo.
            
Tu tarea es clasificar candidatos por:
- Industria
- Área funcional / expertise
- Nivel de seniority
            
Industrias disponibles: Manufacturing, Consumer Goods, Retail, Logistics and Supply Chain, Transportation, Pharmaceutical, Construction, Real Estate, Financial Services, Technology, Hospitality, Industrial Services, Energy, Automotive, Food and Beverage, Professional Services, Healthcare.
            
Áreas funcionales disponibles: General Management, Operations, Manufacturing, Supply Chain, Logistics, Procurement, Sales, Business Development, Marketing, Finance, Accounting, Human Resources, Talent Acquisition, Engineering, Quality, Maintenance, IT, Legal, Customer Service, Project Management, Construction Management.
            
Niveles de seniority: entry, junior, mid, senior, lead, manager, director, vp, c_level.
            
Responde SOLO en formato JSON:
{
    "industry": "industria identificada",
    "functional_area": "área funcional identificada",
    "seniority": "nivel de seniority",
    "confidence_score": 0.85,
    "suggested_tags": ["tag1", "tag2", "tag3"],
    "reasoning": "breve explicación de la clasificación"
}
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

atlas_service = AtlasAIService()