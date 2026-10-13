"""Duplicados probables: solo aviso, nunca fusiona ni borra.

Regla: mismo email o teléfono, O (nombre normalizado donde uno contiene al otro, o primer nombre +
primer apellido iguales) Y ≥ 2 empleadores coincidentes con fechas traslapadas.
"""
import re
import unicodedata
from datetime import date
from typing import Dict, List, Optional, Tuple

from stability_alert import employer_names, parse_period, same_employer

MIN_SHARED_EMPLOYERS = 2
PARTICLES = {'de', 'del', 'la', 'las', 'los', 'van', 'von', 'da', 'di', 'y', 'san'}


def _norm_name(name: Optional[str]) -> str:
    text = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z\s]', ' ', text)).strip()


def _first_last(name: Optional[str]) -> Optional[Tuple[str, str]]:
    tokens = [t for t in _norm_name(name).split() if t not in PARTICLES and len(t) > 1]
    if len(tokens) < 2:
        return None
    return tokens[0], tokens[1]


def _digits(phone: Optional[str]) -> str:
    digits = re.sub(r'\D', '', str(phone or ''))
    return digits[-10:] if len(digits) >= 10 else ''


def _periods(candidate: Dict, today: date) -> List[Tuple[List[str], tuple]]:
    out = []
    for item in candidate.get('previous_companies') or []:
        if not isinstance(item, dict):
            continue
        start, end, _ = parse_period(item.get('start_date'), item.get('end_date'), today)
        if start:
            out.append((employer_names(item.get('company_name')), (start, end)))
    return out


def shared_employers(a: Dict, b: Dict, today: Optional[date] = None) -> List[str]:
    """Empleadores coincidentes con periodos traslapados."""
    today = today or date.today()
    shared = []
    for names_a, (start_a, end_a) in _periods(a, today):
        for names_b, (start_b, end_b) in _periods(b, today):
            if same_employer(names_a, names_b) and start_a <= end_b and start_b <= end_a:
                label = names_a[0]
                if label not in shared:
                    shared.append(label)
                break
    return shared


def duplicate_reason(a: Dict, b: Dict, today: Optional[date] = None) -> Optional[str]:
    email_a, email_b = (a.get('email') or '').strip().lower(), (b.get('email') or '').strip().lower()
    if email_a and email_a == email_b:
        return f'mismo email ({email_a})'
    phone_a, phone_b = _digits(a.get('phone')), _digits(b.get('phone'))
    if phone_a and phone_a == phone_b:
        return f'mismo teléfono (…{phone_a[-4:]})'

    name_a, name_b = _norm_name(a.get('full_name')), _norm_name(b.get('full_name'))
    if not name_a or not name_b:
        return None
    contained = name_a == name_b or (len(min(name_a, name_b, key=len)) >= 6
                                     and min(name_a, name_b, key=len) in max(name_a, name_b, key=len))
    same_core = _first_last(name_a) is not None and _first_last(name_a) == _first_last(name_b)
    if not (contained or same_core):
        return None
    shared = shared_employers(a, b, today)
    if len(shared) >= MIN_SHARED_EMPLOYERS:
        motivo = 'nombre contenido' if contained else 'primer nombre y primer apellido iguales'
        return f'{motivo} + {len(shared)} empleadores coincidentes ({", ".join(shared[:3])})'
    return None


def find_duplicate_pairs(candidates: List[Dict], today: Optional[date] = None) -> List[Dict]:
    """Pares probables (solo lectura). Cada par: nombre A, nombre B y motivo."""
    pairs = []
    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            reason = duplicate_reason(a, b, today)
            if reason:
                pairs.append({'a_id': a.get('id'), 'a_nombre': a.get('full_name'),
                              'b_id': b.get('id'), 'b_nombre': b.get('full_name'), 'motivo': reason})
    return pairs


def collapse_duplicates(rows: List[Dict], docs_by_id: Dict[str, Dict], score_key: str = 'final_score',
                        today: Optional[date] = None) -> List[Dict]:
    """Deja solo la fila con mejor puntuación de cada par y le pone el aviso. No fusiona nada."""
    kept: List[Dict] = []
    for row in rows:
        doc = docs_by_id.get(row.get('candidate_id'))
        twin_index = None
        reason = None
        if doc:
            for index, other in enumerate(kept):
                other_doc = docs_by_id.get(other.get('candidate_id'))
                if not other_doc:
                    continue
                reason = duplicate_reason(doc, other_doc, today)
                if reason:
                    twin_index = index
                    break
        if twin_index is None:
            kept.append(row)
            continue
        twin = kept[twin_index]
        winner, loser = (row, twin) if (row.get(score_key) or 0) > (twin.get(score_key) or 0) else (twin, row)
        winner['duplicate_of'] = {'candidate_id': loser.get('candidate_id'),
                                  'nombre': loser.get('candidate_name') or (docs_by_id.get(loser.get('candidate_id')) or {}).get('full_name'),
                                  'motivo': reason}
        kept[twin_index] = winner
    return kept
