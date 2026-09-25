"""Recupera el CV de una ficha ya absorbida como versión histórica del principal.

Reutiliza `CandidateMerger.preserve_secondary_cv` (misma lógica corregida del merge).
Uso: python3 recover_merged_cv.py <primary_id> <secondary_id>
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import os  # noqa: E402
from duplicate_detector_v2 import CandidateMerger  # noqa: E402
from storage_service import StorageService  # noqa: E402


async def main(primary_id: str, secondary_id: str):
    uri = os.environ.get("ATLAS_URI") or os.environ["MONGO_URL"]
    db_name = os.environ.get("ATLAS_DB_NAME") or os.environ["DB_NAME"]
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    primary = await db.candidates.find_one({"id": primary_id})
    secondary = await db.candidates.find_one({"id": secondary_id})
    if not primary or not secondary:
        raise SystemExit("Ficha no encontrada")

    merger = CandidateMerger(db)
    for cv_file in merger._cv_files(secondary):
        data, content_type = StorageService.get_object(cv_file["file_key"])
        print(f"Archivo disponible en storage: {cv_file['file_name']} ({len(data)} bytes, {content_type})")

    for entry in await merger.preserve_secondary_cv(primary, secondary):
        print(entry)

    versions = await db.cv_versions.find(
        {"candidate_id": primary_id}, {"_id": 0}).sort("version", 1).to_list(50)
    for version in versions:
        print(f"  v{version['version']} | {version['file_name']} | vigente={version['is_current']} "
              f"| origen={version['upload_source']} | de={version.get('merged_from_candidate_id')}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
