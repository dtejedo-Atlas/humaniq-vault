"""Etapa 2: inferencia de subárea con IA para quienes no tienen señal en el puesto.

Reglas del usuario:
- Sólo se infiere la subárea. Nunca área, industria ni seniority.
- Se excluyen las clasificaciones aprobadas por una persona.
- La subárea debe pertenecer al área que ya tiene el candidato.
- Confianza < 0.7 o subárea fuera del área → se deja vacía.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from humaniq_catalog import AREA_BY_KEY, CATALOG_VERSION  # noqa: E402

ACTIVE = {"is_deleted": {"$ne": True}}
MIN_CONFIDENCE = 0.7
CONCURRENCY = 5
MODEL = ("anthropic", "claude-sonnet-4-5-20250929")


def build_prompt(candidate):
    area = AREA_BY_KEY[candidate["presentation_area"]]
    options = "\n".join(f'  - "{sub["key"]}": {sub["label"]}' for sub in area["subareas"])
    skills = ", ".join((candidate.get("skills") or [])[:25])
    return f"""Clasifica la SUBÁREA de este profesional dentro del área "{area['label']}".

PERFIL:
- Puesto actual: {candidate.get('current_title') or 'no disponible'}
- Empresa actual: {candidate.get('current_company') or 'no disponible'}
- Resumen: {(candidate.get('ai_summary') or 'no disponible')[:600]}
- Skills: {skills or 'no disponible'}

SUBÁREAS VÁLIDAS (elige exactamente una 'key' de esta lista, ninguna otra):
{options}

REGLAS:
- No cambies el área: la subárea debe salir de la lista anterior.
- Si la información no alcanza para decidir con seguridad, responde subarea: null.
- confidence es tu seguridad real entre 0 y 1. Sé honesto: preferimos vacío a un error.

Responde SOLO JSON: {{"subarea": "key_o_null", "confidence": 0.0, "razon": "máx 12 palabras"}}"""


async def infer_one(candidate, semaphore, api_key):
    valid_keys = {sub["key"] for sub in AREA_BY_KEY[candidate["presentation_area"]]["subareas"]}
    async with semaphore:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"subarea-{candidate['id']}",
            system_message="Eres un experto en taxonomías de reclutamiento ejecutivo en México. Respondes sólo JSON válido.",
        ).with_model(*MODEL)
        try:
            raw = await chat.send_message(UserMessage(text=build_prompt(candidate)))
        except Exception as error:  # noqa: BLE001
            return {"id": candidate["id"], "status": "error", "detail": str(error)[:160]}

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"id": candidate["id"], "status": "sin_json"}
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return {"id": candidate["id"], "status": "json_invalido"}

        subarea = data.get("subarea")
        confidence = data.get("confidence") or 0
        if not subarea or subarea not in valid_keys:
            return {"id": candidate["id"], "status": "sin_subarea", "confidence": confidence}
        if float(confidence) < MIN_CONFIDENCE:
            return {"id": candidate["id"], "status": "baja_confianza", "confidence": confidence,
                    "subarea": subarea}
        return {"id": candidate["id"], "status": "ok", "subarea": subarea,
                "confidence": float(confidence), "razon": data.get("razon"),
                "area": candidate["presentation_area"], "puesto": candidate.get("current_title")}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="/app/test_reports/subarea_ai_pass.json")
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ.get("ATLAS_URI") or os.environ["MONGO_URL"])
    db = client[os.environ.get("ATLAS_DB_NAME") or os.environ["DB_NAME"]]

    # Nunca se sobrescribe una subárea existente, ni la que ya dedujo la clasificación
    # del CV completo (más rica que el título): sólo se rellenan las realmente vacías.
    query = {**ACTIVE, "presentation_area": {"$ne": None},
             "$or": [{"presentation_subarea": None}, {"presentation_subarea": {"$exists": False}}],
             "ai_classification.presentation_subarea": None}
    projection = {"_id": 0, "id": 1, "full_name": 1, "presentation_area": 1, "current_title": 1,
                  "current_company": 1, "skills": 1, "ai_summary": 1,
                  "ai_classification.approved_by_recruiter": 1}
    candidates = [doc for doc in await db.candidates.find(query, projection).to_list(2000)
                  if (doc.get("ai_classification") or {}).get("approved_by_recruiter") is not True]
    if args.limit:
        candidates = candidates[: args.limit]
    print(f"A procesar: {len(candidates)}", flush=True)

    semaphore = asyncio.Semaphore(CONCURRENCY)
    api_key = os.environ["EMERGENT_LLM_KEY"]
    results = []
    for index in range(0, len(candidates), 50):
        chunk = candidates[index:index + 50]
        results.extend(await asyncio.gather(*(infer_one(c, semaphore, api_key) for c in chunk)))
        print(f"  procesados {min(index + 50, len(candidates))}/{len(candidates)}", flush=True)

    now = datetime.now(timezone.utc).isoformat()
    applied = 0
    if args.apply:
        for item in results:
            if item["status"] != "ok":
                continue
            await db.candidates.update_one({"id": item["id"]}, {"$set": {
                "presentation_subarea": item["subarea"],
                "ai_classification.presentation_subarea": item["subarea"],
                "subarea_source": "ai",
                "subarea_confidence": item["confidence"],
                "taxonomy_version": CATALOG_VERSION,
                "updated_at": now,
            }})
            applied += 1

    report = {
        "modo": "aplicado" if args.apply else "simulacion",
        "procesados": len(results),
        "llenados": applied if args.apply else sum(1 for item in results if item["status"] == "ok"),
        "estado": dict(Counter(item["status"] for item in results)),
        "por_subarea": dict(Counter(f"{item.get('area')}/{item.get('subarea')}"
                                    for item in results if item["status"] == "ok").most_common()),
        "ejemplos": [item for item in results if item["status"] == "ok"][:12],
        "errores": [item for item in results if item["status"] == "error"][:5],
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("ejemplos", "por_subarea")},
                     ensure_ascii=False, indent=1), flush=True)
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
