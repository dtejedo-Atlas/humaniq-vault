"""Aplica las correcciones de nombre aprobadas y purga las fichas de pruebas QA."""
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db
from storage_service import StorageService
from text_utils import normalize_for_search

TEST_PATTERN = re.compile(r"TEST_|Batch[0-9a-f]{6,}|PRUEBA|E2E|Paralela|Repro", re.I)


def strip_accents(value):
    text = unicodedata.normalize("NFKD", (value or "").lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def accent_count(value):
    return sum(1 for c in (value or "") if unicodedata.normalize("NFKD", c) != c)


def main():
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    proposals = json.loads(Path("/app/test_reports/name_fix_proposals.json").read_text())
    scan = json.loads(Path("/app/test_reports/name_quality_scan.json").read_text())

    renamed, skipped = [], []
    for item in proposals:
        proposed = (item.get("nombre_propuesto") or "").strip()
        if not proposed:
            skipped.append({"candidate_id": item["candidate_id"], "motivo": item.get("error", "sin_propuesta")})
            continue

        # Preferir la variante con acentos si el nombre del archivo los trae y la IA los perdió
        from_file = re.sub(r"\.(pdf|docx?)$", "", re.sub(r"^(CV|Cv|Candidato - )\s*", "", item.get("file_name") or ""), flags=re.I).strip()
        if from_file and strip_accents(from_file) == strip_accents(proposed) and accent_count(from_file) > accent_count(proposed):
            proposed = from_file

        candidate = db.candidates.find_one({"id": item["candidate_id"]}, {"_id": 0, "full_name": 1, "email": 1, "phone": 1})
        if not candidate:
            skipped.append({"candidate_id": item["candidate_id"], "motivo": "ficha_no_encontrada"})
            continue

        updates = {"full_name": proposed, "full_name_normalized": normalize_for_search(proposed), "updated_at": now}
        if not candidate.get("email") and item.get("email_propuesto"):
            updates["email"] = item["email_propuesto"]
        if not candidate.get("phone") and item.get("telefono_propuesto"):
            updates["phone"] = item["telefono_propuesto"]

        db.candidates.update_one({"id": item["candidate_id"]}, {"$set": updates})
        renamed.append({"candidate_id": item["candidate_id"], "antes": candidate.get("full_name"),
                        "despues": proposed, "campos": sorted(updates.keys())})
        print(f'  {item["candidate_id"][:8]} {candidate.get("full_name")!r} -> {proposed!r}')

    # ---- Fichas de pruebas QA: soft delete + purga del CV en almacenamiento ----
    qa_rows = [r for r in scan["fichas"] if TEST_PATTERN.search(r["full_name"] or "")]
    purged, purge_errors = [], []
    for row in qa_rows:
        candidate = db.candidates.find_one({"id": row["candidate_id"]}, {"_id": 0, "full_name": 1, "resume_files": 1, "is_deleted": 1})
        if not candidate or candidate.get("is_deleted"):
            continue
        files_purged = 0
        for file in candidate.get("resume_files") or []:
            if not file.get("file_path"):
                continue
            try:
                StorageService.delete_object(file["file_path"])
                files_purged += 1
            except Exception as e:
                purge_errors.append({"candidate_id": row["candidate_id"], "file_path": file["file_path"],
                                     "error": f"{type(e).__name__}: {e}"})
        db.candidates.update_one({"id": row["candidate_id"]}, {"$set": {
            "is_deleted": True, "deleted_at": now, "deleted_by_name": "Limpieza de datos de prueba",
            "deletion_type": "qa_test_data", "deletion_reason": "Ficha sintética de pruebas QA; CV purgado del almacenamiento",
            "updated_at": now,
        }})
        db.cv_hashes.update_many({"candidate_id": row["candidate_id"]}, {"$set": {"active": False}})
        purged.append({"candidate_id": row["candidate_id"], "full_name": candidate.get("full_name"),
                       "cvs_purgados": files_purged})
        print(f'  QA eliminada: {candidate.get("full_name")} ({files_purged} CV purgado/s)')

    result = {
        "nombres_corregidos": len(renamed),
        "nombres_saltados": skipped,
        "fichas_qa_eliminadas": len(purged),
        "cvs_purgados": sum(p["cvs_purgados"] for p in purged),
        "errores_purga": purge_errors,
        "candidatos_activos": db.candidates.count_documents({"is_deleted": {"$ne": True}}),
        "detalle_nombres": renamed,
        "detalle_qa": purged,
    }
    Path("/app/test_reports/name_fix_applied.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n" + json.dumps({k: v for k, v in result.items() if not k.startswith("detalle")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
