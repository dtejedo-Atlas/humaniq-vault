"""Correcciones puntuales de industria aprobadas por el usuario el 2026-10-27.

NO es un reclasificador automático: es una lista cerrada y explícita de cambios.
Respalda cada documento completo antes de tocarlo (colección `doc_backups` + archivo JSON).
Sin --apply solo simula.

Uso:
    python3 -m scripts.apply_industry_fixes
    python3 -m scripts.apply_industry_fixes --apply
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from scripts.db_connection import get_db  # noqa: E402

LOTE = "industry_fixes_2026_10_27"

# (a) y (d): industria del candidato
CANDIDATE_INDUSTRY = {
    "Daniela Adriana Quintero Cruz": "education",
    "Danyella Fernanda Arroyo Gerala": "healthcare",
    "Christian de Jesús Castro Espino": "manufacturing",
    "Marco A. Luna": "manufacturing",
    "Carlos Uribe Bello": "technology",
    "Fernando Padrón Hernández": "food_beverage",
    "Diego Ramírez Bocanegra": "consumer_goods",
    "Alexandra Juarez Huitron": "industrial_services",
    "Teresa Segura Morales": "healthcare",
    # (d) los que afectan el filtro de industria obligatoria
    "Alejandro Cancino Salinas": "manufacturing",
    "Luis Anibal Leal Rojas": "healthcare",
    "Carlos Josué López Solano": "transportation",
}

# (b): etiqueta de la EMPRESA dentro de la trayectoria (la persona ya está bien)
COMPANY_INDUSTRY = {
    "Alberto Curis Montesinos": (["Llano Colorado", "Casa Pedro Domecq"], "food_beverage"),
    "Fernando Bárcenas Rodríguez": (["Del Fruto Distribuidora y Comercializadora Refresquera"], "food_beverage"),
    "Rafael Gonzalez": (["Alimentaria Artesanal SA de CV"], "food_beverage"),
}


def backup(db, doc, apply: bool, carpeta: str):
    if not apply:
        return
    db.doc_backups.insert_one({
        "id": str(uuid.uuid4()),
        "batch": LOTE,
        "collection": "candidates",
        "doc_id": doc["id"],
        "full_name": doc.get("full_name"),
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "document": json.loads(json.dumps(doc, default=str)),
    })
    with open(os.path.join(carpeta, f"{doc['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, default=str)


def main(apply: bool):
    db = get_db()
    carpeta = f"/app/memory/backups/{LOTE}"
    if apply:
        os.makedirs(carpeta, exist_ok=True)

    print(f"\n{'SIMULACIÓN' if not apply else 'APLICANDO'} — {LOTE}\n")
    print(f"{'Candidato':34s} {'Campo':26s} {'Antes':24s} {'Después':24s}")
    print("-" * 112)

    for nombre, nueva in CANDIDATE_INDUSTRY.items():
        doc = db.candidates.find_one({"full_name": nombre, "is_deleted": {"$ne": True}}, {"_id": 0})
        if not doc:
            print(f"{nombre:34s} NO ENCONTRADO")
            continue
        antes = doc.get("industry")
        if antes == nueva:
            print(f"{nombre[:33]:34s} {'industry':26s} {str(antes):24s} {'(ya estaba)':24s}")
            continue
        print(f"{nombre[:33]:34s} {'industry':26s} {str(antes):24s} {nueva:24s}")
        if apply:
            backup(db, doc, apply, carpeta)
            db.candidates.update_one(
                {"id": doc["id"]},
                {"$set": {"industry": nueva,
                          "industry_corrected_at": datetime.now(timezone.utc).isoformat(),
                          "industry_corrected_batch": LOTE}},
            )

    for nombre, (empresas, nueva) in COMPANY_INDUSTRY.items():
        doc = db.candidates.find_one({"full_name": nombre, "is_deleted": {"$ne": True}}, {"_id": 0})
        if not doc:
            print(f"{nombre:34s} NO ENCONTRADO")
            continue
        respaldado = False
        pcs = doc.get("previous_companies") or []
        for idx, p in enumerate(pcs):
            cn = (p.get("company_name") or "")
            if not any(e.lower() in cn.lower() for e in empresas):
                continue
            antes = p.get("company_industry")
            if antes == nueva:
                print(f"{nombre[:33]:34s} {('empresa: ' + cn)[:26]:26s} {str(antes):24s} {'(ya estaba)':24s}")
                continue
            print(f"{nombre[:33]:34s} {('empresa: ' + cn)[:26]:26s} {str(antes):24s} {nueva:24s}")
            if apply:
                if not respaldado:
                    backup(db, doc, apply, carpeta)
                    respaldado = True
                db.candidates.update_one(
                    {"id": doc["id"]},
                    {"$set": {f"previous_companies.{idx}.company_industry": nueva,
                              "industry_corrected_at": datetime.now(timezone.utc).isoformat(),
                              "industry_corrected_batch": LOTE}},
                )

    if apply:
        print(f"\nRespaldos: colección `doc_backups` (batch={LOTE}) y archivos en {carpeta}")
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    main(p.parse_args().apply)
