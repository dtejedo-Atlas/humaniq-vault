"""Detecta fichas con el nombre mal parseado. SOLO LECTURA: genera un informe de propuestas."""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db

PLACEHOLDERS = {"no especificado", "sin nombre", "n/a", "na", "desconocido", "nombre", "candidato", "sin datos"}
FILE_HINTS = re.compile(r"\.(pdf|docx?|rtf|odt)\b|^(cv|curriculum|curriculum vitae|resume|candidato)\b", re.IGNORECASE)
SUSPICIOUS_CHARS = re.compile(r"[0-9_@|/\\]|\(\d+\)")


def issues_for(name):
    issues = []
    clean = (name or "").strip()
    if not clean:
        return ["vacio"]
    low = clean.lower()
    if low in PLACEHOLDERS:
        issues.append("placeholder")
    if FILE_HINTS.search(clean):
        issues.append("nombre_de_archivo")
    if SUSPICIOUS_CHARS.search(clean):
        issues.append("caracteres_invalidos")
    words = clean.split()
    if len(words) == 1:
        issues.append("una_sola_palabra")
    if len(words) > 6:
        issues.append("demasiadas_palabras")
    letters = [c for c in clean if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 3:
        issues.append("todo_mayusculas")
    if letters and all(c.islower() for c in letters):
        issues.append("todo_minusculas")
    if any(unicodedata.category(c) == "Cc" for c in clean) or "  " in clean:
        issues.append("espacios_o_control")
    return issues


def title_case(name):
    small = {"de", "del", "la", "las", "los", "y", "da", "das", "do", "dos", "van", "von"}
    parts = []
    for index, word in enumerate(re.split(r"(\s+|-)", name.strip().lower())):
        if not word.strip() or word == "-":
            parts.append(word)
            continue
        parts.append(word if (word in small and index > 0) else word[0].upper() + word[1:])
    return "".join(parts)


def main():
    db = get_db()
    rows = []
    for c in db.candidates.find(
        {"is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "full_name": 1, "email": 1, "current_title": 1, "resume_files": 1, "created_at": 1}
    ):
        found = issues_for(c.get("full_name"))
        if not found:
            continue
        files = c.get("resume_files") or []
        rows.append({
            "candidate_id": c["id"],
            "full_name": c.get("full_name"),
            "issues": found,
            "email": c.get("email"),
            "current_title": c.get("current_title"),
            "created_at": c.get("created_at"),
            "file_name": files[0].get("file_name") if files else None,
            "file_path": files[0].get("file_path") if files else None,
            "suggestion_casing": title_case(c.get("full_name") or "") if {"todo_mayusculas", "todo_minusculas"} & set(found) else None,
        })

    counts = {}
    for row in rows:
        for issue in row["issues"]:
            counts[issue] = counts.get(issue, 0) + 1

    out = Path("/app/test_reports/name_quality_scan.json")
    out.write_text(json.dumps({"total": len(rows), "por_problema": counts, "fichas": rows},
                              ensure_ascii=False, indent=2))
    print(f"Fichas con nombre sospechoso: {len(rows)}")
    for issue, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {issue:24} {n:>4}")
    print(f"\nDetalle: {out}")


if __name__ == "__main__":
    main()
