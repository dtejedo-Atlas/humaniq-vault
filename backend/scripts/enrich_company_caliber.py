#!/usr/bin/env python3
"""
Batch: infiere company_caliber en previous_companies de candidatos activos en Atlas.
Enriquecimiento ADITIVO: solo escribe company_caliber, no toca ningún otro campo.
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / '.env')

from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage

VALID_CALIBERS = {"multinacional_global", "corporativo_nacional", "mediana", "pyme", "startup"}
BATCH_SIZE = 5

SYSTEM_MESSAGE = """Eres Atlas, experto en el mercado empresarial de México y Latinoamérica.

Clasifica el calibre de cada empresa en UNO de estos 5 valores exactos:
- "multinacional_global": presencia en múltiples países, marca global reconocida
- "corporativo_nacional": gran empresa nacional o filial grande
- "mediana": empresa mediana establecida
- "pyme": pequeña o mediana empresa local
- "startup": empresa joven / emprendimiento

Si no hay información suficiente para clasificar una empresa, responde null para esa empresa. NO inventes.

Responde SOLO con un array JSON de la misma longitud que la lista de empresas, en el mismo orden.
Ejemplo: ["multinacional_global", null, "pyme"]"""


async def infer_calibers(candidate_id: str, companies: list) -> list:
    payload = [
        {
            "company_name": c.get("company_name"),
            "title": c.get("title"),
            "description": (c.get("description") or "")[:300],
        }
        for c in companies
    ]
    chat = LlmChat(
        api_key=os.environ['EMERGENT_LLM_KEY'],
        session_id=f"caliber-{candidate_id}",
        system_message=SYSTEM_MESSAGE,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    message = UserMessage(text=f"Clasifica el calibre de estas empresas:\n{json.dumps(payload, ensure_ascii=False)}")
    response = await chat.send_message(message)

    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    start = text.index("[")
    result, _ = json.JSONDecoder().raw_decode(text[start:])

    if not isinstance(result, list) or len(result) != len(companies):
        raise ValueError(f"Respuesta inválida: esperaba {len(companies)} elementos, recibí {result}")
    return [r if r in VALID_CALIBERS else None for r in result]


async def process_candidate(db, cand) -> dict:
    pcs = cand.get("previous_companies") or []
    missing_idx = [i for i, pc in enumerate(pcs) if pc.get("company_caliber") not in VALID_CALIBERS]
    if not missing_idx:
        return {"processed": False, "inferred": 0, "null": 0, "name": cand.get("full_name")}

    to_classify = [pcs[i] for i in missing_idx]
    try:
        calibers = await infer_calibers(cand["id"], to_classify)
    except Exception as e:
        print(f"  ERROR {cand.get('full_name')}: {e}")
        return {"processed": False, "inferred": 0, "null": 0, "error": True, "name": cand.get("full_name")}

    inferred = 0
    nulls = 0
    for idx, caliber in zip(missing_idx, calibers):
        pcs[idx]["company_caliber"] = caliber
        if caliber:
            inferred += 1
        else:
            nulls += 1

    await db.candidates.update_one(
        {"id": cand["id"]},
        {"$set": {"previous_companies": pcs}}
    )
    return {"processed": True, "inferred": inferred, "null": nulls, "name": cand.get("full_name")}


async def main():
    client = AsyncIOMotorClient(os.environ['ATLAS_URI'])
    db = client[os.environ.get('ATLAS_DB_NAME') or os.environ['DB_NAME']]

    candidates = await db.candidates.find(
        {"is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "full_name": 1, "previous_companies": 1}
    ).to_list(500)

    print(f"Candidatos activos: {len(candidates)}")

    total_processed = 0
    total_skipped = 0
    total_errors = 0
    total_inferred = 0
    total_null = 0

    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i:i + BATCH_SIZE]
        results = await asyncio.gather(*[process_candidate(db, c) for c in batch])
        for r in results:
            if r.get("error"):
                total_errors += 1
            elif r["processed"]:
                total_processed += 1
                total_inferred += r["inferred"]
                total_null += r["null"]
            else:
                total_skipped += 1
        print(f"Lote {i // BATCH_SIZE + 1}: {min(i + BATCH_SIZE, len(candidates))}/{len(candidates)} candidatos")

    print("\n===== RESUMEN =====")
    print(f"Candidatos procesados (con update): {total_processed}")
    print(f"Candidatos sin empresas pendientes (skip): {total_skipped}")
    print(f"Candidatos con error: {total_errors}")
    print(f"Empresas con calibre inferido: {total_inferred}")
    print(f"Empresas en null (info insuficiente): {total_null}")


if __name__ == "__main__":
    asyncio.run(main())
