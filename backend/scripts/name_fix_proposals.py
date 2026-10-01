"""Propone el nombre real leyendo el CV de las fichas con nombre mal parseado. NO aplica cambios."""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db
from storage_service import StorageService
from document_parser import DocumentParser
from atlas_service import atlas_service

TEST_PATTERN = re.compile(r"TEST_|Batch[0-9a-f]{6,}|PRUEBA|E2E|Paralela|Repro", re.I)


async def main():
    db = get_db()
    scan = json.loads(Path("/app/test_reports/name_quality_scan.json").read_text())
    rows = [r for r in scan["fichas"] if not TEST_PATTERN.search(r["full_name"] or "")]
    print(f"Fichas reales a revisar: {len(rows)}")

    proposals = []
    for row in rows:
        entry = {
            "candidate_id": row["candidate_id"],
            "nombre_actual": row["full_name"],
            "file_name": row["file_name"],
            "problemas": row["issues"],
        }
        if not row["file_path"]:
            entry["error"] = "sin_cv"
            proposals.append(entry)
            continue
        try:
            data, content_type = StorageService.get_object(row["file_path"])
            text = DocumentParser.extract_text_from_bytes(data, content_type) or ""
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
            proposals.append(entry)
            continue

        entry["primeras_lineas"] = " | ".join(
            [line.strip() for line in text.splitlines() if line.strip()][:4]
        )[:220]
        try:
            parsed = await atlas_service.parse_resume(text[:6000])
            entry["nombre_propuesto"] = (parsed.get("full_name") or "").strip() or None
            entry["email_propuesto"] = parsed.get("email")
            entry["telefono_propuesto"] = parsed.get("phone")
        except Exception as e:
            entry["error"] = f"ai: {type(e).__name__}: {e}"
        proposals.append(entry)
        print(f"  {row['candidate_id'][:8]} {row['full_name']!r} -> {entry.get('nombre_propuesto')!r}")

    out = Path("/app/test_reports/name_fix_proposals.json")
    out.write_text(json.dumps(proposals, ensure_ascii=False, indent=2))
    print(f"\nPropuestas: {out}")


if __name__ == "__main__":
    asyncio.run(main())
