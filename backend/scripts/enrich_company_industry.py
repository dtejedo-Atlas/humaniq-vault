#!/usr/bin/env python3
"""Backfill: infiere company_industry (clave del catálogo o null) por empleo en previous_companies.

Misma pasada/estilo que enrich_company_caliber.py. Modelo: Claude Sonnet 5.5 (Emergent LLM Key).
Uso: python scripts/enrich_company_industry.py [--limit N] [--force]
"""
import os
import sys
import json
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / '.env')

from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage
from taxonomy import INDUSTRIES

MODEL = "claude-sonnet-5-5"
BATCH_SIZE = 5
VALID = {i["key"] for i in INDUSTRIES}
CATALOG = "\n".join(f"- {i['key']}: {i['name_es']}" for i in INDUSTRIES)

SYSTEM_MESSAGE = f"""Eres Atlas, experto en el mercado empresarial de México y Latinoamérica.
Para cada empresa recibes nombre, puesto y descripción del empleo. Debes indicar la INDUSTRIA DE LA EMPRESA
(no la función del candidato) usando EXCLUSIVAMENTE una de estas claves del catálogo:
{CATALOG}

Reglas:
- Usa el conocimiento que tengas de la empresa (ej. Telcel → telecommunications, Dell → technology, Clip → fintech,
  Coca-Cola → consumer_goods, BBVA → financial_services, Rappi → technology).
- fintech = empresas cuyo producto principal es financiero y tecnológico (pagos digitales, neobancos, crédito digital).
  Bancos y aseguradoras tradicionales → financial_services.
- Si el nombre es genérico o anonimizado ("Empresa multinacional de empaque") decide por la descripción.
- Si no tienes certeza razonable, responde la cadena "desconocida". No inventes.
- Responde ÚNICAMENTE un arreglo JSON de strings con la misma longitud y orden que la entrada.
  Ejemplo: ["telecommunications", "desconocida", "consumer_goods"]"""


async def infer_industries(candidate_id, companies):
    payload = [{"company_name": c.get("company_name"), "title": c.get("title"),
                "description": (c.get("description") or "")[:300]} for c in companies]
    chat = LlmChat(api_key=os.environ['EMERGENT_LLM_KEY'], session_id=f"industry-{candidate_id}",
                   system_message=SYSTEM_MESSAGE).with_model("anthropic", MODEL)
    response = await chat.send_message(UserMessage(text=f"Clasifica la industria de estas empresas:\n{json.dumps(payload, ensure_ascii=False)}"))
    text = response.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    result, _ = json.JSONDecoder().raw_decode(text[text.index("["):])
    if not isinstance(result, list) or len(result) != len(companies):
        raise ValueError(f"Respuesta inválida: esperaba {len(companies)} elementos, recibí {result}")
    return [r if r in VALID else None for r in result]


async def process_candidate(db, cand, force):
    pcs = cand.get("previous_companies") or []
    idx = [i for i, pc in enumerate(pcs) if force or "company_industry" not in pc]
    idx = [i for i in idx if pcs[i].get("company_name") or pcs[i].get("description")]
    if not idx:
        return {"processed": False, "name": cand.get("full_name")}
    try:
        inds = await infer_industries(cand["id"], [pcs[i] for i in idx])
    except ValueError:
        # El modelo colapsó duplicados: inferir una por una
        try:
            inds = [(await infer_industries(f"{cand['id']}-{i}", [pcs[i]]))[0] for i in idx]
        except Exception as e:
            print(f"  ERROR {cand.get('full_name')}: {e}")
            return {"processed": False, "error": True, "name": cand.get("full_name")}
    except Exception as e:
        print(f"  ERROR {cand.get('full_name')}: {e}")
        return {"processed": False, "error": True, "name": cand.get("full_name")}
    inferred = nulls = 0
    for i, ind in zip(idx, inds):
        pcs[i]["company_industry"] = ind
        inferred += ind is not None
        nulls += ind is None
    await db.candidates.update_one({"id": cand["id"]}, {"$set": {"previous_companies": pcs}})
    return {"processed": True, "inferred": inferred, "null": nulls, "name": cand.get("full_name")}


async def main():
    force = "--force" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    client = AsyncIOMotorClient(os.environ['ATLAS_URI'])
    db = client[os.environ.get('ATLAS_DB_NAME') or os.environ['DB_NAME']]
    candidates = await db.candidates.find({"is_deleted": {"$ne": True}, "previous_companies.0": {"$exists": True}},
                                          {"_id": 0, "id": 1, "full_name": 1, "previous_companies": 1}).to_list(5000)
    if limit:
        candidates = candidates[:limit]
    print(f"Candidatos con empleos: {len(candidates)} | modelo {MODEL}")
    t0 = time.time()
    stats = {"processed": 0, "skipped": 0, "errors": 0, "inferred": 0, "null": 0}
    for i in range(0, len(candidates), BATCH_SIZE):
        results = await asyncio.gather(*[process_candidate(db, c, force) for c in candidates[i:i + BATCH_SIZE]])
        for r in results:
            if r.get("error"):
                stats["errors"] += 1
            elif r["processed"]:
                stats["processed"] += 1
                stats["inferred"] += r["inferred"]
                stats["null"] += r["null"]
            else:
                stats["skipped"] += 1
        print(f"Lote {i // BATCH_SIZE + 1}: {min(i + BATCH_SIZE, len(candidates))}/{len(candidates)} | {int(time.time() - t0)}s", flush=True)
    print("\n===== RESUMEN =====")
    print(json.dumps(stats, indent=1), f"\nTiempo total: {int(time.time() - t0)}s")


if __name__ == "__main__":
    asyncio.run(main())
