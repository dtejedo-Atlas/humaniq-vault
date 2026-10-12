"""Deduplicación de experiencia laboral para fusiones de fichas.

Mismo empleo = empresa normalizada similar (una contiene a la otra, sin acentos ni sufijos de
razón social) + periodos que se traslapan. Se conserva el registro más completo.
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


def dedupe_experience(entries: List[Dict]) -> List[Dict]:
    """Agrupa empleos equivalentes y conserva el registro más completo de cada grupo."""
    groups: List[List[Dict]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        for group in groups:
            if any(is_same_job(entry, member) for member in group):
                group.append(entry)
                break
        else:
            groups.append([entry])

    kept = []
    for group in groups:
        best = max(group, key=_richness)
        for member in group:
            if member is not best:
                best = _merge_pair(best, member)
        kept.append(best)
    kept.sort(key=lambda e: e.get('start_date') or '', reverse=True)
    return kept
