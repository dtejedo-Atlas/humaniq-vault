"""Alerta de estabilidad laboral: informativa, NO cambia score, ranking ni acción.

Cuenta EMPLEADORES distintos (no puestos) en los últimos 5 y 10 años. Sin IA.
No toca calculate_stability_score ni calculate_stability_penalty.
"""
import calendar
import re
import unicodedata
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

RED_5Y, YELLOW_5Y = 3, 3          # >3 rojo, ==3 amarillo
RED_10Y, YELLOW_10Y = 5, 5        # >5 rojo, ==5 amarillo
MIN_WINDOW_MONTHS = 3
SHORT_STAY_MONTHS = 12
GAP_MONTHS = 6
NO_CURRENT_JOB_MONTHS = 2

LEGAL_SUFFIXES = ('s a de c v', 's de r l de c v', 'sa de cv', 'sapi de cv', 'inc', 'llc', 'ltd', 'plc',
                  'corp', 'corporation', 'company', 'co', 'group', 'grupo', 'mexico', 'latam',
                  'latinoamerica', 'americas', 'international', 'global', 'holding', 'holdings', 'the')
TRAILING_TOKENS = {'s', 'a', 'b', 'c', 'v', 'p', 'i', 'r', 'l', 'de', 'y'}
ALIAS_PATTERN = re.compile(r'\((?:formerly|antes|ahora|now|ex)\s+([^)]+)\)', re.IGNORECASE)
PRESENT = ('presente', 'present', 'actual', 'actualidad', 'current', 'currently', 'hoy', 'a la fecha', 'to date')
BOARD_WORDS = ('miembro del consejo', 'consejo de administracion', 'board member', 'board of directors',
               'advisory', 'advisor', 'asesor', 'consejero')
CONSULTING_WORDS = ('consultor', 'consultant', 'consulting', 'consultoria', 'freelance', 'independiente',
                    'independent', 'socio fundador', 'fundador', 'founder', 'propio')
PARALLEL_WORDS = ('en paralelo', 'in parallel', 'simultane')
MONTHS = {'ene': 1, 'jan': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7,
          'ago': 8, 'aug': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12, 'dec': 12}


def _ascii(text: Optional[str]) -> str:
    return unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode().lower()


def normalize_employer(name: Optional[str]) -> str:
    text = ALIAS_PATTERN.sub(' ', _ascii(name))
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    changed = True
    while changed:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            if text.endswith(' ' + suffix):
                text, changed = text[: -len(suffix) - 1].strip(), True
            elif text.startswith(suffix + ' '):
                text, changed = text[len(suffix) + 1:].strip(), True
        tokens = text.split()
        while len(tokens) > 1 and tokens[-1] in TRAILING_TOKENS:
            tokens.pop()
            changed = True
        text = ' '.join(tokens)
    return text


def employer_names(raw: Optional[str]) -> List[str]:
    """Nombre normalizado + alias de '(Formerly X)', '(antes X)', '(ahora X)'."""
    names = [normalize_employer(raw)]
    for alias in ALIAS_PATTERN.findall(raw or ''):
        names.append(normalize_employer(alias))
    return [n for n in names if n]


def same_employer(a: List[str], b: List[str]) -> bool:
    for x in a:
        for y in b:
            if x == y:
                return True
            short, long_ = sorted((x, y), key=len)
            if len(short) >= 4 and short in long_:
                return True
    return False


def _month_year(value: str) -> Optional[Tuple[int, int, bool]]:
    """(año, mes, solo_año) de 'AAAA-MM', 'MM/AAAA', 'oct 2023', 'AAAA'."""
    text = _ascii(value).strip()
    m = re.match(r'^(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?$', text)
    if m:
        return int(m.group(1)), min(max(int(m.group(2)), 1), 12), False
    m = re.match(r'^(\d{1,2})[-/](\d{4})$', text)
    if m:
        return int(m.group(2)), min(max(int(m.group(1)), 1), 12), False
    m = re.match(r'^([a-z]{3,})\.?\s+(?:de\s+)?(\d{4})$', text)
    if m and m.group(1)[:3] in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1)[:3]], False
    m = re.match(r'^(\d{4})$', text)
    if m:
        return int(m.group(1)), 0, True
    return None


def parse_period(start_raw, end_raw, today: date) -> Tuple[Optional[date], Optional[date], bool]:
    """Fechas de inicio/fin según las reglas del aviso. Devuelve (inicio, fin, fechas_aproximadas)."""
    start_info = _month_year(str(start_raw)) if start_raw else None
    end_text = _ascii(str(end_raw)) if end_raw else ''
    end_is_present = (not end_raw) or any(w in end_text for w in PRESENT)
    end_info = None if end_is_present else _month_year(str(end_raw))
    if not start_info:
        return None, None, False

    approx = start_info[2] or bool(end_info and end_info[2])
    same_year_only = start_info[2] and end_info and end_info[2] and start_info[0] == end_info[0]
    if same_year_only:
        return date(start_info[0], 4, 1), date(start_info[0], 9, 30), True

    start = date(start_info[0], 7, 1) if start_info[2] else date(start_info[0], start_info[1], 1)
    if end_is_present:
        end = today
    elif end_info:
        end = date(end_info[0], 7, 1) if end_info[2] else \
            date(end_info[0], end_info[1], calendar.monthrange(end_info[0], end_info[1])[1])
    else:
        end = today
    if end < start:
        start, end = end, start
    return start, min(end, today), approx


def _months(start: date, end: date) -> float:
    return max(0.0, (end - start).days / 30.44)


def _merge(periods: List[Tuple[date, date]]) -> List[Tuple[date, date]]:
    merged: List[Tuple[date, date]] = []
    for start, end in sorted(periods):
        if merged and start <= merged[-1][1] + timedelta(days=31):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _covered(period: Tuple[date, date], others: List[Tuple[date, date]]) -> bool:
    """True si todo el periodo está cubierto por la unión de los otros empleos."""
    start, end = period
    for o_start, o_end in _merge(others):
        if o_start <= start + timedelta(days=31):
            start = max(start, o_end)
    return start >= end - timedelta(days=31)


def _entries(candidate: Dict, today: date) -> List[Dict]:
    history = list(candidate.get('previous_companies') or [])
    current_name = candidate.get('current_company')
    if current_name and not any(same_employer(employer_names(current_name), employer_names(p.get('company_name')))
                                for p in history):
        history.insert(0, {'company_name': current_name, 'title': candidate.get('current_title'),
                           'start_date': None, 'end_date': None, '_from_current': True})
    entries = []
    for item in history:
        if not isinstance(item, dict):
            continue
        start, end, approx = parse_period(item.get('start_date'), item.get('end_date'), today)
        if start is None:
            continue
        text = _ascii(f"{item.get('title') or ''} {item.get('description') or ''}")
        consulting = any(w in text for w in CONSULTING_WORDS)
        entries.append({'names': employer_names(item.get('company_name')) or [_ascii(item.get('company_name'))],
                        'label': item.get('company_name') or 'Sin empresa', 'start': start, 'end': end,
                        'approx': approx, 'text': text,
                        # La consultoría propia se evalúa aparte: no se trata como rol de consejo
                        'board': any(w in text for w in BOARD_WORDS) and not consulting,
                        'consulting': consulting,
                        'explicit_parallel': any(w in text for w in PARALLEL_WORDS)})
    return entries


def compute_stability_alert(candidate: Dict, today: Optional[date] = None) -> Dict:
    today = today or date.today()
    entries = _entries(candidate, today)
    parallel, counted = [], []

    # Consejo/advisory cubierto por otros empleos, o marcado "en paralelo"
    for entry in entries:
        others = [(e['start'], e['end']) for e in entries if e is not entry]
        if entry['explicit_parallel'] or (entry['board'] and _covered((entry['start'], entry['end']), others)):
            entry['reason'] = 'Rol en consejo/asesoría dentro de otro empleo' if not entry['explicit_parallel'] \
                else 'La descripción indica que fue en paralelo'
            parallel.append(entry)
        else:
            counted.append(entry)

    # Consultoría/empresa propia: no cuenta si todo su periodo coincide con los empleos que sí cuentan
    survivors = []
    for entry in counted:
        others = [(e['start'], e['end']) for e in counted if e is not entry]
        if entry['consulting'] and _covered((entry['start'], entry['end']), others):
            entry['reason'] = 'Consultoría simultánea a otro empleo'
            parallel.append(entry)
        else:
            survivors.append(entry)

    # Agrupar por empleador
    groups: List[Dict] = []
    for entry in survivors:
        for group in groups:
            if same_employer(entry['names'], group['names']):
                group['names'] = list(dict.fromkeys(group['names'] + entry['names']))
                group['periods'].append((entry['start'], entry['end']))
                break
        else:
            groups.append({'names': list(entry['names']), 'label': entry['label'],
                           'periods': [(entry['start'], entry['end'])]})

    def employers_in(years: int) -> int:
        window_start = today - timedelta(days=round(365.25 * years))
        total = 0
        for group in groups:
            overlap = sum(_months(max(s, window_start), min(e, today))
                          for s, e in _merge(group['periods']) if e > window_start)
            if overlap >= MIN_WINDOW_MONTHS:
                total += 1
        return total

    employers_5y, employers_10y = employers_in(5), employers_in(10)
    if employers_5y > RED_5Y or employers_10y > RED_10Y:
        level, texto = 'rojo', (f"{employers_5y} empleadores en 5 años (máx. {RED_5Y})" if employers_5y > RED_5Y
                                else f"{employers_10y} empleadores en 10 años (máx. {RED_10Y})")
    elif employers_5y == YELLOW_5Y or employers_10y == YELLOW_10Y:
        level = 'amarillo'
        texto = (f"{employers_5y} empleadores en 5 años (límite {YELLOW_5Y})" if employers_5y == YELLOW_5Y
                 else f"{employers_10y} empleadores en 10 años (límite {YELLOW_10Y})")
    else:
        level, texto = 'verde', f"{employers_5y} empleadores en 5 años"

    window_5y = today - timedelta(days=round(365.25 * 5))
    short_stays = [{'empleador': e['label'], 'meses': round(_months(e['start'], e['end']))}
                   for e in survivors
                   if e['end'] > window_5y and _months(e['start'], e['end']) < SHORT_STAY_MONTHS]

    window_10y = today - timedelta(days=round(365.25 * 10))
    gaps = []
    merged_all = _merge([(e['start'], e['end']) for e in survivors])
    for (_, end_a), (start_b, _) in zip(merged_all, merged_all[1:]):
        if start_b > end_a and end_a > window_10y and _months(end_a, start_b) >= GAP_MONTHS:
            gaps.append({'desde': end_a.isoformat(), 'hasta': start_b.isoformat(),
                         'meses': round(_months(end_a, start_b))})
    last_end = max((e['end'] for e in entries), default=None)
    no_current = bool(last_end and _months(last_end, today) > NO_CURRENT_JOB_MONTHS)

    timeline = [{'empleador': e['label'], 'inicio': e['start'].isoformat(), 'fin': e['end'].isoformat(),
                 'meses': round(_months(e['start'], e['end'])), 'cuenta': e in survivors,
                 'motivo_no_cuenta': e.get('reason')}
                for e in sorted(entries, key=lambda x: x['start'], reverse=True)]

    return {'level': level, 'employers_5y': employers_5y, 'employers_10y': employers_10y,
            'timeline': timeline,
            'roles_paralelos': [{'empleador': e['label'], 'inicio': e['start'].isoformat(),
                                 'fin': e['end'].isoformat(), 'motivo': e.get('reason')} for e in parallel],
            'estancias_cortas': short_stays, 'huecos': gaps, 'sin_empleo_actual': no_current,
            'fechas_aproximadas': any(e['approx'] for e in entries), 'texto': texto}
