#!/usr/bin/env python3
"""Batch: normaliza skills en inglés a español estándar de reclutamiento (solo campo skills)."""
import os
import sys
import json
import asyncio
import re
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / '.env')

from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage

EN_TOKENS = {
    'management','planning','leadership','budgeting','forecasting','treasury','cash','flow',
    'supply','chain','accounting','reporting','analysis','compliance','sourcing','procurement',
    'negotiation','strategy','strategic','development','improvement','customer','service',
    'sales','pricing','training','recruiting','payroll','accounts',
    'receivable','payable','audit','auditing','risk','banking','investment','financial',
    'modeling','building','team','process','project','stakeholder','vendor','inventory',
    'warehouse','logistics','distribution','demand','cost','reduction','continuous','business',
    'communication','skills','problem','solving','decision','making'
}
NEUTRAL = {'sap','excel','power','bi','crm','erp','sql','python','aws','azure','scrum','agile',
           'lean','six','sigma','kaizen','tpm','wms','tms','oracle','salesforce','hubspot',
           'niif','ifrs','usgaap','gaap','kpi','kpis','okr','okrs','b2b','b2c','mrp','plc','iso','haccp',
           'marketing','retail','trade','intelligence','compliance'}


def has_english_skill(skills):
    for s in skills or []:
        words = [w for w in re.findall(r'[a-záéíóúñü]+', s.lower()) if w not in NEUTRAL]
        if words and sum(1 for w in words if w in EN_TOKENS) >= max(1, len(words) / 2):
            return True
    return False


SYSTEM = """Eres un experto en taxonomía de habilidades para reclutamiento ejecutivo en México.
Recibirás una lista de skills de un candidato. Devuelve la MISMA lista (mismo orden, misma longitud)
con cada skill normalizado a español estándar de reclutamiento en México.

REGLAS:
1. Traduce los skills en inglés: "Treasury Management" -> "Gestión de Tesorería", "Cash Flow Management" -> "Gestión de flujo de efectivo", "Supply Chain Management" -> "Gestión de cadena de suministro", "Budgeting" -> "Presupuestos", "Team Leadership" -> "Liderazgo de equipos".
2. CONSERVA tal cual los anglicismos de uso estándar en el medio mexicano: Marketing, Trade Marketing, Retail, Compliance, Business Intelligence, Forecasting (cuando es término técnico establecido, prefiere el español: "Pronósticos").
3. CONSERVA nombres propios de herramientas/sistemas/metodologías: SAP, Excel, Power BI, Salesforce, Six Sigma, Lean Manufacturing, Scrum, NIIF/IFRS, KPIs.
4. Los skills que ya están en español correcto se devuelven sin cambios.

Responde SOLO con JSON: {"skills": ["...", "..."]} — misma cantidad de elementos que la entrada."""


async def normalize_skills(cid, skills):
    chat = LlmChat(
        api_key=os.environ['EMERGENT_LLM_KEY'],
        session_id=f"skills-es-{cid}",
        system_message=SYSTEM,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    resp = await chat.send_message(UserMessage(text=json.dumps({"skills": skills}, ensure_ascii=False)))
    text = resp.strip()
    start = text.find('{')
    result, _ = json.JSONDecoder().raw_decode(text[start:])
    out = result.get('skills')
    if not isinstance(out, list) or len(out) != len(skills):
        raise ValueError(f"longitud inesperada: {len(out) if isinstance(out, list) else out}")
    return [str(s).strip() for s in out]


async def main():
    client = AsyncIOMotorClient(os.environ['ATLAS_URI'])
    db = client[os.environ['ATLAS_DB_NAME']]
    targets = []
    async for c in db.candidates.find({'is_deleted': {'$ne': True}}, {'_id': 0, 'id': 1, 'full_name': 1, 'skills': 1}):
        if has_english_skill(c.get('skills')):
            targets.append(c)
    print(f"Candidatos a normalizar: {len(targets)}")

    sem = asyncio.Semaphore(4)
    mappings = Counter()
    changed_candidates = 0
    errors = []

    async def worker(c):
        nonlocal changed_candidates
        async with sem:
            try:
                new_skills = await normalize_skills(c['id'], c['skills'])
            except Exception as e:
                errors.append((c['full_name'], str(e)[:120]))
                return
            diffs = [(o, n) for o, n in zip(c['skills'], new_skills) if o != n]
            if diffs:
                await db.candidates.update_one({'id': c['id']}, {'$set': {'skills': new_skills}})
                changed_candidates += 1
                for o, n in diffs:
                    mappings[f"{o} -> {n}"] += 1

    await asyncio.gather(*[worker(c) for c in targets])

    print(f"\nCandidatos modificados: {changed_candidates}")
    print(f"Skills traducidos (únicos): {len(mappings)} | total instancias: {sum(mappings.values())}")
    print("\nTop 30 mapeos:")
    for m, n in mappings.most_common(30):
        print(f"  {m}  (x{n})")
    if errors:
        print(f"\nErrores ({len(errors)}):")
        for name, e in errors:
            print(f"  {name}: {e}")


if __name__ == '__main__':
    asyncio.run(main())
