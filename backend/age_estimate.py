"""Edad estimada: informativa, NO cambia score, ranking ni acción. Sin IA y sin tocar el parser.

Usa solo datos ya existentes en el candidato. No se persiste en el documento.
"""
import re
import unicodedata
from datetime import date
from typing import Dict, Optional

AGE_NOTICE_CAREER_YEARS = 25     # notificación si los años desde el primer empleo son > 25
AGE_NOTICE_ESTIMATED = 50        # notificación si la edad estimada (punto medio) es >= 50

GRADUATION_AGE = 23
FIRST_JOB_AGE = 22
EXPERIENCE_BASE_AGE = 22
INTERN_WORDS = ('practicante', 'practicas', 'becario', 'trainee', 'intern', 'internship', 'pasante',
                'residencia profesional', 'servicio social')
BACHELOR_WORDS = ('licenciatura', 'licenciado', 'ingenieria', 'ingeniero', 'bachelor', 'bsc', 'b sc',
                  'carrera', 'universidad', 'university', 'titulo profesional')


def _ascii(text: Optional[str]) -> str:
    return unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()


def _year(value) -> Optional[int]:
    match = re.search(r'(19|20)\d{2}', str(value or ''))
    year = int(match.group(0)) if match else None
    return year if year and 1940 <= year <= date.today().year + 6 else None


def _explicit_age(candidate: Dict, today: date) -> Optional[Dict]:
    for key in ('age', 'edad'):
        raw = candidate.get(key)
        try:
            age = int(float(raw))
        except (TypeError, ValueError):
            continue
        if 16 <= age <= 90:
            return {'edad_estimada': age, 'rango_min': age, 'rango_max': age, 'fuente': 'nacimiento',
                    'detalle': f'Edad declarada en el CV ({age})', 'confianza': 'alta'}
    for key in ('birth_date', 'date_of_birth', 'fecha_nacimiento', 'birth_year', 'anio_nacimiento'):
        year = _year(candidate.get(key))
        if year:
            age = today.year - year
            if 16 <= age <= 90:
                return {'edad_estimada': age, 'rango_min': age, 'rango_max': age, 'fuente': 'nacimiento',
                        'detalle': f'Fecha de nacimiento en el CV ({year})', 'confianza': 'alta'}
    return None


def _graduation(candidate: Dict, today: date) -> Optional[Dict]:
    best = None
    for item in candidate.get('education') or []:
        if not isinstance(item, dict):
            continue
        text = _ascii(f"{item.get('degree')} {item.get('level')} {item.get('field')} {item.get('institution')}")
        year = _year(item.get('graduation_year') or item.get('year') or item.get('end_date') or item.get('to'))
        if not year or not any(w in text for w in BACHELOR_WORDS):
            continue
        if best is None or year < best[0]:
            best = (year, item.get('degree') or item.get('level') or 'Licenciatura',
                    item.get('institution') or '')
    if not best:
        return None
    age = (today.year - best[0]) + GRADUATION_AGE
    return {'edad_estimada': age, 'rango_min': age - 2, 'rango_max': age + 2, 'fuente': 'egreso',
            'detalle': f'Egreso {best[0]} ({best[1]}{" · " + best[2] if best[2] else ""})'.strip(),
            'confianza': 'media'}


def first_job_year(candidate: Dict) -> Optional[tuple]:
    """Año del empleo más antiguo (ignorando prácticas/becario) y nombre de la empresa."""
    best = None
    for item in candidate.get('previous_companies') or []:
        if not isinstance(item, dict):
            continue
        title = _ascii(item.get('title'))
        if any(w in title for w in INTERN_WORDS):
            continue
        year = _year(item.get('start_date'))
        if year and (best is None or year < best[0]):
            best = (year, item.get('company_name') or '')
    return best


def estimate_age(candidate: Dict, today: Optional[date] = None) -> Dict:
    today = today or date.today()
    first_job = first_job_year(candidate)
    career_years = (today.year - first_job[0]) if first_job else None
    try:
        declared_years = int(float(candidate.get('years_experience')))
    except (TypeError, ValueError):
        declared_years = None
    if declared_years is not None and declared_years <= 0:
        declared_years = None

    estimate = _explicit_age(candidate, today) or _graduation(candidate, today)
    if estimate is None and first_job:
        # Los CV ejecutivos listan solo los últimos 10-15 años: el primer empleo listado subestima
        # la carrera, así que se toma el mayor entre ese lapso y los años declarados.
        if declared_years is not None:
            career_years = max(career_years, declared_years)
        age = career_years + FIRST_JOB_AGE
        detalle = f'Primer empleo {first_job[0]}' + (f' ({first_job[1]})' if first_job[1] else '')
        if declared_years is not None and declared_years > (today.year - first_job[0]):
            detalle = (f'{declared_years} años de experiencia declarados · '
                       f'primer empleo listado {first_job[0]}')
        estimate = {'edad_estimada': age, 'rango_min': age - 3, 'rango_max': age + 3, 'fuente': 'primer_empleo',
                    'detalle': detalle, 'confianza': 'media'}
    if estimate is None and declared_years is not None:
        age = declared_years + EXPERIENCE_BASE_AGE
        estimate = {'edad_estimada': age, 'rango_min': age - 4, 'rango_max': age + 4,
                    'fuente': 'years_experience',
                    'detalle': f'{declared_years} años de experiencia declarados', 'confianza': 'baja'}
        career_years = career_years if career_years is not None else declared_years
    if estimate is None:
        return {'edad_estimada': None, 'rango_min': None, 'rango_max': None, 'fuente': None, 'detalle': None,
                'confianza': None, 'años_carrera': None, 'notificacion': False}

    midpoint = (estimate['rango_min'] + estimate['rango_max']) / 2
    notice = bool((career_years is not None and career_years > AGE_NOTICE_CAREER_YEARS)
                  or midpoint >= AGE_NOTICE_ESTIMATED)
    return {**estimate, 'años_carrera': career_years, 'notificacion': notice}
