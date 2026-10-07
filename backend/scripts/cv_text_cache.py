"""Extrae y cachea el texto completo de los CVs vigentes (solo lectura sobre Atlas).

Salida privada: /root/humaniq_cv_diagnosis/cv_texts.json  {candidate_id: {"text", "key", "version", "error"}}
Uso: python scripts/cv_text_cache.py [--workers 6]
"""
import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import get_db  # noqa: E402
from document_parser import DocumentParser  # noqa: E402
from resume_read_safety import read_original  # noqa: E402

OUT = Path("/root/humaniq_cv_diagnosis/cv_texts.json")


def _reference(db, candidate):
    version = db.cv_versions.find_one({"candidate_id": candidate["id"], "is_current": True, "is_active": True}, {"_id": 0})
    if version and version.get("file_key"):
        return {"key": version["file_key"], "type": version.get("file_type") or version.get("mime_type")
                or Path(version.get("file_name") or version["file_key"]).suffix.lstrip("."), "version": version.get("id")}
    files = candidate.get("resume_files") or []
    if not files:
        return None
    resume = max(enumerate(files), key=lambda it: (str(it[1].get("upload_date") or ""), it[0]))[1]
    return {"key": resume.get("file_path"), "type": resume.get("file_type") or Path(resume.get("file_name") or "").suffix.lstrip("."),
            "version": resume.get("id") or resume.get("file_path")}


def _extract(ref):
    raw = read_original(ref)
    det = DocumentParser.extract_with_details(raw, ref["type"] or "pdf")
    return det.get("text") or ""


def main(workers=6):
    db = get_db()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(OUT.read_text()) if OUT.exists() else {}
    cands = list(db.candidates.find({"is_deleted": {"$ne": True}}, {"_id": 0, "id": 1, "resume_files": 1}))
    todo = []
    for c in cands:
        ref = _reference(db, c)
        if not ref:
            cache[c["id"]] = {"text": "", "error": "sin_cv", "key": None, "version": None}
            continue
        prev = cache.get(c["id"])
        if prev and prev.get("key") == ref["key"] and prev.get("text"):
            continue
        todo.append((c["id"], ref))
    print(f"total={len(cands)} pendientes={len(todo)}")

    def work(item):
        cid, ref = item
        try:
            return cid, {"text": _extract(ref), "key": ref["key"], "version": ref["version"], "error": None}
        except Exception as e:  # noqa: BLE001
            return cid, {"text": "", "key": ref["key"], "version": ref["version"], "error": str(e)[:200]}

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for cid, res in ex.map(work, todo):
            cache[cid] = res
            done += 1
            if done % 25 == 0:
                OUT.write_text(json.dumps(cache, ensure_ascii=False))
                print(f"progreso {done}/{len(todo)}", flush=True)
    OUT.write_text(json.dumps(cache, ensure_ascii=False))
    ok = sum(1 for v in cache.values() if v.get("text"))
    print(f"listo: {ok} con texto, {len(cache) - ok} sin texto")


if __name__ == "__main__":
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    main(w)
