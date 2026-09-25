"""Inventario y migración de la taxonomía Humaniq.

Por defecto SOLO LEE. Con --apply-it corrige `it` → `technology` (autorizado).
Con --apply-presentation rellena los campos de presentación (aditivo, no cambia
`functional_area`). Nunca reescribe áreas distintas de `it` sin autorización.
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db_connection import get_db  # noqa: E402
from humaniq_catalog import ENGINE_AREAS, resolve_area, resolve_seniority, CATALOG_VERSION  # noqa: E402

ACTIVE = {"is_deleted": {"$ne": True}}


def inventory(db):
    areas = Counter()
    seniorities = Counter()
    missing_presentation = 0
    for doc in db.candidates.find(ACTIVE, {"_id": 0, "functional_area": 1, "seniority": 1, "presentation_area": 1}):
        areas[doc.get("functional_area")] += 1
        seniorities[doc.get("seniority")] += 1
        if doc.get("functional_area") and not doc.get("presentation_area"):
            missing_presentation += 1
    return {
        "total_active": sum(areas.values()),
        "by_functional_area": dict(areas.most_common()),
        "non_engine_areas": {key: count for key, count in areas.items()
                             if key and key not in ENGINE_AREAS},
        "by_seniority": dict(seniorities.most_common()),
        "sin_presentation_area": missing_presentation,
        "jobs_by_functional_area": dict(Counter(
            job.get("functional_area") for job in db.jobs.find({}, {"_id": 0, "functional_area": 1})).most_common()),
    }


def apply_it_fix(db):
    """Autorizado por el usuario: `it` → `technology` en candidatos y su clasificación."""
    now = datetime.now(timezone.utc).isoformat()
    top = db.candidates.update_many(
        {"functional_area": "it"},
        {"$set": {"functional_area": "technology", "presentation_area": "tecnologia",
                  "taxonomy_version": CATALOG_VERSION, "updated_at": now}})
    nested = db.candidates.update_many(
        {"ai_classification.functional_area": "it"},
        {"$set": {"ai_classification.functional_area": "technology",
                  "ai_classification.presentation_area": "tecnologia",
                  "ai_classification.taxonomy_version": CATALOG_VERSION, "updated_at": now}})
    jobs = db.jobs.update_many(
        {"functional_area": "it"},
        {"$set": {"functional_area": "technology", "presentation_area": "tecnologia", "updated_at": now}})
    return {"candidatos_campo_principal": top.modified_count,
            "candidatos_ai_classification": nested.modified_count,
            "vacantes": jobs.modified_count}


def apply_presentation_backfill(db):
    """Aditivo: deriva área/subárea/seniority de presentación. No cambia functional_area."""
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    unresolved = Counter()
    for doc in db.candidates.find(ACTIVE, {"_id": 0, "id": 1, "functional_area": 1, "seniority": 1,
                                           "presentation_area": 1, "presentation_seniority": 1}):
        updates = {}
        if doc.get("functional_area") and not doc.get("presentation_area"):
            area = resolve_area(doc["functional_area"])
            if area:
                updates["presentation_area"] = area["presentation_area"]
                updates["presentation_subarea"] = area["presentation_subarea"]
            else:
                unresolved[f"area:{doc['functional_area']}"] += 1
        if doc.get("seniority") and not doc.get("presentation_seniority"):
            seniority = resolve_seniority(doc["seniority"])
            if seniority:
                updates["presentation_seniority"] = seniority["presentation_seniority"]
            else:
                unresolved[f"seniority:{doc['seniority']}"] += 1
        if updates:
            updates["taxonomy_version"] = CATALOG_VERSION
            updates["updated_at"] = now
            db.candidates.update_one({"id": doc["id"]}, {"$set": updates})
            updated += 1
    return {"candidatos_actualizados": updated, "sin_resolver": dict(unresolved)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-it", action="store_true")
    parser.add_argument("--apply-presentation", action="store_true")
    parser.add_argument("--out", default="/app/test_reports/humaniq_taxonomy_migration.json")
    args = parser.parse_args()

    db = get_db()
    report = {"executed_at": datetime.now(timezone.utc).isoformat(), "before": inventory(db)}
    if args.apply_it:
        report["it_to_technology"] = apply_it_fix(db)
    if args.apply_presentation:
        report["presentation_backfill"] = apply_presentation_backfill(db)
    if args.apply_it or args.apply_presentation:
        report["after"] = inventory(db)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
