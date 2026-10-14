"""Deduplicación de experiencia laboral para fusiones de fichas.

Mismo empleo = empresa normalizada similar (una contiene a la otra, sin acentos ni sufijos de
razón social) + periodos que se traslapan. Se conserva el registro más completo y la trayectoria
interna (título más reciente + lista de roles en la descripción).

`dedupe_experience` se usa SOLO en el flujo de fusión de fichas (duplicate_detector_v2) y en el
script de limpieza. Nunca corre al cargar un CV ni al calcular el ranking.
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

SUFFIXES = (
    'sa de cv', 'sapi de cv', 's de rl de cv', 'sa', 'sab', 'sapi', 'srl', 'sc', 'ag', 'gmbh',
    'inc', 'llc', 'ltd', 'plc', 'corp', 'corporation', 'company', 'co', 'group', 'grupo',
    'mexico', 'latam', 'latinoamerica', 'americas', 'de mexico', 'international', 'global',
    'holding', 'holdings', 'smiths', 'the',
)


TRAILING_TOKENS = {'s', 'a', 'b', 'c', 'v', 'p', 'i', 'r', 'l', 'de', 'y'}


def normalize_company(name: Optional[str]) -> str:
    text = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    changed = True
    while changed:
        changed = False
        for suffix in SUFFIXES:
            if text.endswith(' ' + suffix):
                text = text[: -len(suffix) - 1].strip()
                changed = True
            elif text.startswith(suffix + ' '):
                text = text[len(suffix) + 1:].strip()
                changed = True
        # Razones sociales abreviadas sueltas: "s a de c v", "s de r l de c v"
        tokens = text.split()
        while len(tokens) > 1 and tokens[-1] in TRAILING_TOKENS:
            tokens.pop()
            changed = True
        text = ' '.join(tokens)
    return text


def _month(value: Optional[str]) -> Optional[int]:
    """Convierte 'YYYY-MM', 'YYYY', 'oct 2014', 'actual'… en un entero de meses comparable."""
    from industry_trajectory import parse_date
    if value is None or not isinstance(value, (str, int)):
        return None
    parsed = parse_date(str(value))
    return parsed.year * 12 + parsed.month if parsed else None


def _range(entry: Dict) -> Tuple[Optional[int], Optional[int]]:
    return _month(entry.get('start_date')), _month(entry.get('end_date'))


def periods_overlap(a: Dict, b: Dict) -> bool:
    """Mismo periodo = mismo inicio, o traslape real de 2+ meses (un mes contiguo es un ascenso)."""
    a_start, a_end = _range(a)
    b_start, b_end = _range(b)
    if a_start is None or b_start is None:
        # Sin fechas comparables: se consideran el mismo empleo si la empresa coincide.
        return True
    if a_start == b_start:
        return True
    a_end = a_end if a_end is not None else 10 ** 6
    b_end = b_end if b_end is not None else 10 ** 6
    return (min(a_end, b_end) - max(a_start, b_start) + 1) >= 2


def same_company(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = normalize_company(a), normalize_company(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = sorted((na, nb), key=len)
    return len(shorter) >= 4 and shorter in longer


def is_same_job(a: Dict, b: Dict) -> bool:
    return same_company(a.get('company_name'), b.get('company_name')) and periods_overlap(a, b)


def _richness(entry: Dict) -> tuple:
    filled = sum(1 for key in ('title', 'start_date', 'end_date', 'description', 'company_industry',
                               'company_caliber', 'location', 'duration', 'industry')
                 if entry.get(key))
    return (filled, len(str(entry.get('description') or '')), len(str(entry.get('company_name') or '')))


def _merge_pair(keep: Dict, other: Dict) -> Dict:
    """Completa los campos vacíos del registro conservado con los del duplicado."""
    merged = dict(keep)
    for key, value in (other or {}).items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def _year(value: Optional[str]) -> Optional[int]:
    months = _month(value)
    return months // 12 if months else None


def _role_line(entry: Dict) -> str:
    start, end = _year(entry.get('start_date')), _year(entry.get('end_date'))
    title = str(entry.get('title') or 'Puesto sin título').strip()
    if start and end:
        return f"{title} {start}–{end}"
    if start:
        return f"{title} {start}–actualidad"
    return title


def _preserve_trajectory(group: List[Dict], kept: Dict) -> Dict:
    """Conserva la trayectoria interna: título del puesto más reciente + lista de roles."""
    titles = []
    for entry in group:
        title = str(entry.get('title') or '').strip()
        if title and title.lower() not in [t.lower() for t in titles]:
            titles.append(title)
    if len(titles) < 2:
        return kept

    ordered = sorted(group, key=lambda e: _month(e.get('start_date')) or 0, reverse=True)
    result = dict(kept)
    newest_title = str(ordered[0].get('title') or '').strip()
    if newest_title:
        result['title'] = newest_title

    seen, roles = set(), []
    for entry in ordered:
        line = _role_line(entry)
        if line.lower() not in seen:
            seen.add(line.lower())
            roles.append(line)
    roles_text = 'Roles: ' + '; '.join(roles)
    description = str(result.get('description') or '').strip()
    if 'Roles:' not in description:
        result['description'] = f"{description}\n{roles_text}".strip() if description else roles_text
    result['merged_roles'] = roles
    return result


def collapse_strict_duplicates(history: List[Dict], tolerance: int = 2) -> List[Dict]:
    """Colapsa el MISMO empleo listado dos veces (±N meses), conservando el registro más completo.

    Se queda con la entrada de descripción más larga, completa sus campos vacíos con los del resto
    y anota los títulos distintos en la descripción ("También listado como: …").
    Mantiene el orden original del historial.
    """
    groups = strict_duplicates(history, tolerance)
    if not groups:
        return list(history or [])

    replacement, drop = {}, set()
    for group in groups:
        best = max(group, key=lambda e: (len(str(e.get('description') or '')), _richness(e)))
        merged = dict(best)
        for member in group:
            if member is not best:
                merged = _merge_pair(merged, member)
        otros = []
        for member in group:
            title = str(member.get('title') or '').strip()
            if title and title.casefold() != str(merged.get('title') or '').strip().casefold() \
                    and title not in otros:
                otros.append(title)
        if otros:
            nota = 'También listado como: ' + '; '.join(otros)
            description = str(merged.get('description') or '').strip()
            if nota not in description:
                merged['description'] = f"{description}\n{nota}".strip() if description else nota
        # El registro conservado ocupa la posición de la primera aparición (no se mueve el orden)
        first = group[0]
        replacement[id(first)] = merged
        for member in group[1:]:
            drop.add(id(member))

    kept = []
    for entry in history or []:
        if id(entry) in drop:
            continue
        kept.append(replacement.get(id(entry), entry))
    return kept


def experience_years_from_history(history: List[Dict], today_months: Optional[int] = None) -> Optional[int]:
    """Años de experiencia = lapso del primer empleo (sin prácticas) al último, menos huecos de 12+ meses.

    Nunca devuelve más que ese lapso: un valor mayor es señal de inflación por empleos duplicados.
    """
    from datetime import date
    if today_months is None:
        today = date.today()
        today_months = today.year * 12 + today.month

    periods = []
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get('title') or '').lower()
        if any(word in title for word in ('practicante', 'prácticas', 'practicas', 'becario', 'intern', 'trainee')):
            continue
        start, end = _range(entry)
        if start is None:
            continue
        periods.append((start, min(end or today_months, today_months)))
    if not periods:
        return None

    periods.sort()
    span = max(end for _, end in periods) - periods[0][0]
    gaps = 0
    reach = periods[0][1]
    for start, end in periods[1:]:
        if start - reach >= 12:
            gaps += start - reach
        reach = max(reach, end)
    return max(0, round((span - gaps) / 12))


def dedupe_experience(entries: List[Dict]) -> List[Dict]:
    """Agrupa empleos equivalentes y conserva el registro más completo de cada grupo.

    El agrupamiento es transitivo y por tanto independiente del orden del historial: si un
    registro "paraguas" (p. ej. 2005-2019 en la misma empresa) coincide con varios puestos
    internos, todos quedan en el mismo grupo.
    """
    groups: List[List[Dict]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        matched = [g for g in groups if any(is_same_job(entry, member) for member in g)]
        if not matched:
            groups.append([entry])
            continue
        first = matched[0]
        first.append(entry)
        for extra in matched[1:]:
            first.extend(extra)
            groups.remove(extra)

    kept = []
    for group in groups:
        best = max(group, key=_richness)
        for member in group:
            if member is not best:
                best = _merge_pair(best, member)
        kept.append(_preserve_trajectory(group, best))
    kept.sort(key=lambda e: e.get('start_date') or '', reverse=True)
    return kept


def strict_duplicates(history: List[Dict], tolerance: int = 2) -> List[List[Dict]]:
    """Regla estricta: mismo empleador + inicio y fin dentro de ±N meses (el mismo empleo repetido)."""
    groups: List[List[Dict]] = []
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        start, end = _range(entry)
        placed = False
        for group in groups:
            for member in group:
                m_start, m_end = _range(member)
                if not same_company(entry.get('company_name'), member.get('company_name')):
                    continue
                if start is None or m_start is None or abs(start - m_start) > tolerance:
                    continue
                if (end is None) != (m_end is None):
                    continue
                if end is not None and abs(end - m_end) > tolerance:
                    continue
                group.append(entry)
                placed = True
                break
            if placed:
                break
        if not placed:
            groups.append([entry])
    return [g for g in groups if len(g) > 1]
