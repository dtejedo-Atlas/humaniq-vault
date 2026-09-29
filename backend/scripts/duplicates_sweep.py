"""Barrido de duplicados: candidatos con 2 o más fichas activas. SOLO LECTURA."""
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db_connection import get_db  # noqa: E402

ACTIVE = {"is_deleted": {"$ne": True}}


def norm(value):
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def main():
    db = get_db()
    by_email = defaultdict(list)
    by_name = defaultdict(list)
    for doc in db.candidates.find(ACTIVE, {"_id": 0, "id": 1, "full_name": 1, "email": 1,
                                           "created_at": 1, "current_title": 1, "status": 1}):
        if doc.get("email"):
            by_email[norm(doc["email"])].append(doc)
        if doc.get("full_name"):
            by_name[norm(doc["full_name"])].append(doc)

    groups = {}
    for key, docs in list(by_email.items()) + list(by_name.items()):
        if len(docs) < 2:
            continue
        ids = tuple(sorted(item["id"] for item in docs))
        groups[ids] = {
            "nombre": docs[0].get("full_name"),
            "email": docs[0].get("email"),
            "fichas": len(docs),
            "clave": "email" if key in by_email and by_email[key] is docs else "nombre",
            "registros": sorted(
                [{"id": item["id"], "creada": item.get("created_at"),
                  "puesto": item.get("current_title"), "status": item.get("status")}
                 for item in docs], key=lambda item: str(item["creada"])),
        }

    ordered = sorted(groups.values(), key=lambda item: -item["fichas"])
    report = {"grupos": len(ordered),
              "fichas_implicadas": sum(item["fichas"] for item in ordered),
              "duplicados_a_fusionar": sum(item["fichas"] - 1 for item in ordered),
              "detalle": ordered}
    Path("/app/test_reports/duplicates_sweep.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Grupos con 2+ fichas activas: {report['grupos']} | "
          f"fichas implicadas: {report['fichas_implicadas']} | "
          f"sobrantes si se fusionan: {report['duplicados_a_fusionar']}\n")
    for group in ordered:
        fechas = ", ".join(str(item["creada"])[:16] for item in group["registros"])
        print(f"{group['fichas']}x | {group['nombre']} | {group['email']} | {fechas}")


if __name__ == "__main__":
    main()
