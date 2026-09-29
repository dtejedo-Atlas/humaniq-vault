"""Barrido de duplicados por nombre tras la limpieza de CV idénticos. SOLO LECTURA."""
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db  # noqa: E402

ACTIVE = {"is_deleted": {"$ne": True}}


def norm(value):
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def main():
    db = get_db()
    by_name = defaultdict(list)
    for doc in db.candidates.find(ACTIVE, {"_id": 0, "id": 1, "full_name": 1, "email": 1,
                                           "created_at": 1, "current_title": 1, "status": 1}):
        if doc.get("full_name"):
            by_name[norm(doc["full_name"])].append(doc)

    buckets = {"mismo_email": [], "emails_distintos": [], "sin_email": []}
    for key, docs in by_name.items():
        if len(docs) < 2:
            continue
        emails = {norm(d.get("email")) for d in docs if d.get("email")}
        if not emails:
            bucket = "sin_email"
        elif len(emails) == 1:
            bucket = "mismo_email"
        else:
            bucket = "emails_distintos"
        buckets[bucket].append({
            "nombre": docs[0].get("full_name"),
            "fichas": len(docs),
            "emails": sorted(emails),
            "registros": sorted(
                [{"id": d["id"], "creada": d.get("created_at"), "email": d.get("email"),
                  "puesto": d.get("current_title"), "status": d.get("status")} for d in docs],
                key=lambda item: str(item["creada"])),
        })

    for value in buckets.values():
        value.sort(key=lambda g: -g["fichas"])

    report = {
        "resumen": {
            k: {"grupos": len(v), "fichas": sum(g["fichas"] for g in v),
                "sobrantes": sum(g["fichas"] - 1 for g in v)}
            for k, v in buckets.items()
        },
        "detalle": buckets,
    }
    Path("/app/test_reports/duplicates_sweep_by_email.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f'{"categoria":18} {"grupos":>7} {"fichas":>7} {"sobrantes":>10}')
    total = [0, 0, 0]
    for k, s in report["resumen"].items():
        print(f'{k:18} {s["grupos"]:>7} {s["fichas"]:>7} {s["sobrantes"]:>10}')
        total = [total[0] + s["grupos"], total[1] + s["fichas"], total[2] + s["sobrantes"]]
    print(f'{"TOTAL":18} {total[0]:>7} {total[1]:>7} {total[2]:>10}')
    print("\nDetalle: /app/test_reports/duplicates_sweep_by_email.json")


if __name__ == "__main__":
    main()
