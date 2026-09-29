"""Inferencia de subárea Humaniq en dos etapas.

Etapa 1 (esta, gratis): coincidencia determinista por texto del puesto, skills y
resumen contra las subáreas de LA MISMA área que ya tiene el candidato.
Etapa 2 (pendiente de autorización): LLM para los que queden vacíos.

Reglas del usuario:
- Sólo se infiere la subárea. Nunca se toca área, industria ni seniority.
- Se excluyen las clasificaciones aprobadas por una persona.
- La subárea debe pertenecer al área actual del candidato.
- Sin coincidencia clara → se deja vacía (no se adivina).
"""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db_connection import get_db  # noqa: E402
from humaniq_catalog import AREA_BY_KEY, CATALOG_VERSION, _fold  # noqa: E402

ACTIVE = {"is_deleted": {"$ne": True}}
MIN_TOKEN = 5  # tokens más cortos son ambiguos ("ppm", "erp", "m&a")
STOPWORDS = {"y", "de", "en", "otros", "general", "social"}
EXTRA_TOKENS = {
    "contabilidad": ["contador", "contable", "contaduria"],
    "contraloria": ["controller", "contralor"],
    "tesoreria": ["tesorero", "cash management"],
    "atraccion_talento": ["reclutamiento", "reclutador", "talent acquisition", "headhunting"],
    "compensaciones": ["compensacion", "nomina", "payroll"],
    "logistica": ["logistico", "distribucion", "transporte", "trafico"],
    "compras": ["comprador", "abastecimiento", "procurement", "sourcing"],
    "desarrollo_negocio": ["business development", "desarrollo de negocio"],
    "ventas_campo": ["ejecutivo de ventas", "representante de ventas"],
    "produccion": ["produccion", "manufactura", "planta"],
    "calidad": ["aseguramiento de calidad", "control de calidad"],
    "mantenimiento": ["mantenimiento"],
    "seguridad_industrial": ["seguridad industrial", "seguridad e higiene"],
    "desarrollo_software": ["desarrollador", "programador", "software engineer", "fullstack"],
    "infraestructura": ["infraestructura", "redes", "sysadmin"],
    "ciberseguridad": ["ciberseguridad", "seguridad de la informacion"],
    "datos_analitica": ["analitica", "data analyst", "data scientist", "business intelligence"],
    "soporte_ti": ["mesa de ayuda", "help desk", "soporte tecnico"],
    "atencion_cliente": ["atencion a clientes", "servicio al cliente", "customer service"],
    "direccion_obra": ["residente de obra", "superintendente de obra", "director de obra"],
}


def subarea_tokens(area_key):
    """Tokens de búsqueda por subárea del área indicada."""
    tokens = {}
    for subarea in AREA_BY_KEY[area_key]["subareas"]:
        raw = [subarea["label"]]
        raw += re.split(r"[/()]", subarea["label"])
        raw += EXTRA_TOKENS.get(subarea["key"], [])
        cleaned = set()
        for piece in raw:
            folded = _fold(piece).replace("_", " ").strip()
            if len(folded) >= MIN_TOKEN and folded not in STOPWORDS:
                cleaned.add(folded)
        tokens[subarea["key"]] = sorted(cleaned, key=len, reverse=True)
    return tokens


TOKENS_BY_AREA = {area: subarea_tokens(area) for area in AREA_BY_KEY}


def infer_subarea(candidate, use_skills=False):
    """Devuelve (subarea, token, campo) o (None, None, None) si no hay señal clara.

    Por defecto sólo se usa el PUESTO: las listas de skills son largas y genéricas,
    y un solo skill secuestra la subárea ('Contralor' acababa en FP&A).
    """
    area = candidate.get("presentation_area")
    if not area or area not in TOKENS_BY_AREA:
        return None, None, None
    fields = [("titulo", _fold(candidate.get("current_title") or "").replace("_", " "))]
    if use_skills:
        fields.append(("skills", _fold(" ".join(candidate.get("skills") or [])).replace("_", " ")))
    best = (0, None, None, None)
    for subarea, tokens in TOKENS_BY_AREA[area].items():
        for token in tokens:
            for field_name, text in fields:
                if not text or token not in text:
                    continue
                weight = 3 if field_name == "titulo" else 1
                score = len(token) * weight
                if score > best[0]:
                    best = (score, subarea, token, field_name)
    return best[1], best[2], best[3]


def run(db, apply_changes, use_skills=False):
    # Nunca se sobrescribe una subárea existente, ni la que ya dedujo la clasificación
    # del CV completo (más rica que el título): sólo se rellenan las realmente vacías.
    query = {**ACTIVE, "presentation_area": {"$ne": None},
             "$or": [{"presentation_subarea": None}, {"presentation_subarea": {"$exists": False}}],
             "ai_classification.presentation_subarea": None}
    projection = {"_id": 0, "id": 1, "full_name": 1, "presentation_area": 1, "current_title": 1,
                  "skills": 1, "ai_summary": 1, "ai_classification.approved_by_recruiter": 1}
    now = datetime.now(timezone.utc).isoformat()
    filled, skipped_approved, unresolved = 0, 0, 0
    by_area = Counter()
    samples = []

    for doc in db.candidates.find(query, projection):
        if (doc.get("ai_classification") or {}).get("approved_by_recruiter") is True:
            skipped_approved += 1
            continue
        subarea, token, field = infer_subarea(doc, use_skills)
        if not subarea:
            unresolved += 1
            continue
        filled += 1
        by_area[f"{doc['presentation_area']}/{subarea}"] += 1
        if len(samples) < 40:
            samples.append({"nombre": doc.get("full_name"), "puesto": doc.get("current_title"),
                            "area": doc["presentation_area"], "subarea": subarea,
                            "coincidencia": token, "campo": field})
        if apply_changes:
            db.candidates.update_one({"id": doc["id"]}, {"$set": {
                "presentation_subarea": subarea,
                "ai_classification.presentation_subarea": subarea,
                "subarea_source": f"keyword:{field}",
                "taxonomy_version": CATALOG_VERSION,
                "updated_at": now,
            }})

    return {"modo": "aplicado" if apply_changes else "simulacion",
            "rellenables": filled, "sin_senal_clara": unresolved,
            "excluidos_por_aprobacion_humana": skipped_approved,
            "detalle": dict(by_area.most_common()), "muestras": samples}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--use-skills", action="store_true")
    parser.add_argument("--out", default="/app/test_reports/subarea_keyword_pass.json")
    args = parser.parse_args()
    report = run(get_db(), args.apply, args.use_skills)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "muestras"}, ensure_ascii=False, indent=1))
    for sample in report["muestras"][:12]:
        print(f"  {sample['puesto']!r} → {sample['area']}/{sample['subarea']} "
              f"(por {sample['campo']}: {sample['coincidencia']!r})")


if __name__ == "__main__":
    main()
