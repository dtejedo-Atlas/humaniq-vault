"""Industria por trayectoria: afinidad de industria basada en los últimos 10 años de empleo.

Módulo independiente de `scoring/` (no modifica el motor). Lo consumen la simulación de Fase 2,
el aviso de cobertura (Fase 4) y, tras aprobación, `calculate_ia`.
"""
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from affinity_matrices import get_industry_transferability

WINDOW_YEARS = 10
RECENCY_FLOOR = 0.4           # peso del año más antiguo de la ventana (el actual pesa 1.0)
TRAJECTORY_WEIGHT = 0.65      # mezcla: proporción ponderada vs transferibilidad actual
TRANSFER_WEIGHT = 0.35
NEUTRAL_INDIFFERENT = 0.75

_PRESENT = {"present", "presente", "actual", "actualidad", "current", "now", "hoy", "a la fecha", "vigente"}
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"])}
_MONTHS.update({"jan": 1, "apr": 4, "aug": 8, "dec": 12, "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
                "octubre": 10, "noviembre": 11, "diciembre": 12})


def parse_date(value, now: Optional[datetime] = None) -> Optional[datetime]:
    """Acepta YYYY, YYYY-MM, YYYY-MM-DD, MM/YYYY, 'mar 2019', 'Presente'. None si no se entiende."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip().lower()
    if not s or s == "none":
        return None
    if s in _PRESENT:
        return (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    m = re.match(r"^(\d{4})(?:[-/](\d{1,2}))?(?:[-/](\d{1,2}))?$", s)
    if m:
        return _safe(int(m.group(1)), int(m.group(2) or 1))
    m = re.match(r"^(\d{1,2})[/-](\d{4})$", s)
    if m:
        return _safe(int(m.group(2)), int(m.group(1)))
    m = re.match(r"^([a-záéíóú]+)\.?\s+(?:de\s+)?(\d{2,4})$", s)
    if m and m.group(1)[:3] in _MONTHS or (m and m.group(1) in _MONTHS):
        year = int(m.group(2))
        year = year + 2000 if year < 100 else year
        return _safe(year, _MONTHS.get(m.group(1)) or _MONTHS.get(m.group(1)[:3]) or 1)
    m = re.search(r"(\d{4})", s)
    return _safe(int(m.group(1)), 1) if m else None


def _safe(year: int, month: int) -> Optional[datetime]:
    if year < 1950 or year > 2100:
        return None
    return datetime(year, min(max(month, 1), 12), 1)


def job_target_industries(job: Dict) -> Tuple[List[str], str]:
    """Lista de industrias objetivo + requisito. Compatible con el campo legado `industry`."""
    sc = job.get("job_scorecard") or {}
    targets = [t for t in (sc.get("target_industries") or job.get("target_industries") or []) if t]
    if not targets and job.get("industry"):
        targets = [job["industry"]]
    requirement = sc.get("industry_requirement") or job.get("industry_requirement") or "preferente"
    return targets, requirement


def trajectory_profile(candidate: Dict, now: Optional[datetime] = None) -> List[Dict]:
    """Empleos de los últimos 10 años con industria, años dentro de la ventana y peso por recencia."""
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    window_start = datetime(now.year - WINDOW_YEARS, now.month, 1)
    rows = []
    seen = set()
    companies = candidate.get("previous_companies") or []
    for idx, pc in enumerate(companies):
        dedupe_key = ((pc.get("company_name") or "").strip().lower(), str(pc.get("start_date")), str(pc.get("end_date")))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        start = parse_date(pc.get("start_date"), now)
        end = parse_date(pc.get("end_date"), now)
        is_current = pc.get("is_current") or pc.get("end_date") in (None, "") or (end and end >= now)
        if end is None:
            end = now if (is_current or idx == 0) else None
        if start is None and end is None:
            continue
        if start is None:
            start = end
        if end is None:
            end = start
        if end < start:
            start, end = end, start
        ov_start, ov_end = max(start, window_start), min(end, now)
        if ov_end <= ov_start:
            continue
        years = (ov_end - ov_start).days / 365.25
        mid = ov_start + (ov_end - ov_start) / 2
        age = (now - mid).days / 365.25
        recency = 1.0 - (1.0 - RECENCY_FLOOR) * min(max(age / WINDOW_YEARS, 0.0), 1.0)
        industry = pc.get("company_industry")
        if not industry and idx == 0 and is_current:
            industry = candidate.get("industry")
        rows.append({
            "company": pc.get("company_name") or pc.get("company"),
            "title": pc.get("title") or pc.get("position"),
            "industry": industry,
            "start": pc.get("start_date"),
            "end": pc.get("end_date") or "actual",
            "years": round(years, 1),
            "recency": round(recency, 3),
            "weighted_years": years * recency,
        })
    # Empleo actual ausente en previous_companies (CV desactualizado): nunca se inventan años
    covers_now = any(r["end"] == "actual" or (parse_date(r["end"], now) and parse_date(r["end"], now) >= now) for r in rows)
    if not covers_now and candidate.get("industry") and (candidate.get("current_company") or candidate.get("current_title")):
        start = parse_date(candidate.get("current_start_date"), now)
        if start and start < now:
            years = (now - max(start, window_start)).days / 365.25
            rows.append({"company": candidate.get("current_company"), "title": candidate.get("current_title"),
                         "industry": candidate.get("industry"), "start": candidate.get("current_start_date"), "end": "actual",
                         "years": round(years, 1), "recency": 1.0, "weighted_years": years})
        else:
            rows.append({"company": candidate.get("current_company"), "title": candidate.get("current_title"),
                         "industry": candidate.get("industry"), "start": "sin fecha", "end": "actual",
                         "years": 1.0, "recency": 1.0, "weighted_years": 1.0, "undated": True})
    return rows


def industry_affinity(candidate: Dict, job: Dict, now: Optional[datetime] = None) -> Tuple[float, float, Dict]:
    """(xi, ci, evidence) para IA. xi en [0,1]."""
    targets, requirement = job_target_industries(job)
    if not targets:
        return (0.52, 0.0, {"note": "Vacante sin industria objetivo"})
    if requirement == "indiferente":
        return (NEUTRAL_INDIFFERENT, 1.0, {"note": "Industria indiferente para la vacante", "targets": targets})

    rows = trajectory_profile(candidate, now)
    cand_industry = candidate.get("industry")
    transfer = max((get_industry_transferability(cand_industry, t) for t in targets), default=35) / 100.0 \
        if cand_industry else 0.35

    total_w = sum(r["weighted_years"] for r in rows)
    known_w = sum(r["weighted_years"] for r in rows if r["industry"])
    target_rows = [r for r in rows if r["industry"] in targets]
    target_w = sum(r["weighted_years"] for r in target_rows)
    target_years = sum(r["years"] for r in target_rows)

    if total_w <= 0:
        xi = transfer
        ci = 0.45 if cand_industry else 0.0
        return (round(xi, 4), ci, {"note": "Sin historial fechado; solo transferibilidad actual",
                                   "targets": targets, "transferability": round(transfer, 3),
                                   "target_years": 0.0, "evidence": []})

    proportion = target_w / total_w

    xi = TRAJECTORY_WEIGHT * proportion + TRANSFER_WEIGHT * transfer
    ci = 0.5 + 0.5 * (known_w / total_w)
    undated = [r for r in rows if r.get("undated")]
    if undated:
        ci = min(ci, 0.6)
    evidence = {
        "targets": targets,
        "requirement": requirement,
        "proportion_weighted": round(proportion, 3),
        "target_years": round(target_years, 1),
        "transferability": round(transfer, 3),
        "current_industry": cand_industry,
        "evidence": [{**{k: r[k] for k in ("company", "industry", "start", "end", "years")},
                      **({"note": "sin fecha"} if r.get("undated") else {})} for r in target_rows],
        "unknown_industry_jobs": [r["company"] for r in rows if not r["industry"]],
        "undated_current_job": bool(undated),
    }
    return (round(min(1.0, xi), 4), round(ci, 3), evidence)


def industry_knockout(candidate: Dict, job: Dict, now: Optional[datetime] = None) -> Optional[Dict]:
    """Knockout 'importante' cuando la industria es obligatoria y no hay experiencia en ninguna objetivo."""
    targets, requirement = job_target_industries(job)
    if requirement != "obligatoria" or not targets:
        return None
    xi, ci, ev = industry_affinity(candidate, job, now)
    has_target = (ev.get("target_years") or 0) > 0 or candidate.get("industry") in targets
    if has_target:
        return {"criterion": "industry", "status": "cumple", "k_value": 1.0,
                "note": f"{ev.get('target_years', 0)} años en industria objetivo"}
    if ci < 0.5:
        return {"criterion": "industry", "status": "evidencia_insuficiente", "k_value": 0.85,
                "note": "Sin industria conocida en la trayectoria"}
    return {"criterion": "industry", "status": "no_cumple_importante", "k_value": 0.5,
            "note": f"Sin experiencia en {', '.join(targets)} en los últimos {WINDOW_YEARS} años"}


def coverage_by_industry(candidates: List[Dict], targets: List[str], now: Optional[datetime] = None) -> Dict:
    """Cuántos candidatos tienen experiencia (últimos 10 años) por industria objetivo."""
    per = {t: 0 for t in targets}
    any_count = 0
    for c in candidates:
        rows = trajectory_profile(c, now)
        found = {r["industry"] for r in rows if r["industry"] in targets}
        if c.get("industry") in targets:
            found.add(c["industry"])
        for t in found:
            per[t] += 1
        if found:
            any_count += 1
    return {"per_industry": per, "any": any_count}
