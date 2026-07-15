"""
Script de migración para agregar 'key' canónica a la taxonomía existente
y actualizar las colecciones industries y functional_areas.

Este script:
1. Borra la taxonomía existente (sin key)
2. Inserta la nueva taxonomía con keys canónicas desde taxonomy.py
3. Actualiza los candidatos existentes para mapear los nombres antiguos a keys
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Mapeo de nombres antiguos (en inglés) a keys canónicas
OLD_INDUSTRY_TO_KEY = {
    "Manufacturing": "manufacturing",
    "Manufactura": "manufacturing",
    "Consumer Goods": "consumer_goods",
    "Bienes de Consumo": "consumer_goods",
    "Retail": "retail",
    "Logistics and Supply Chain": "logistics_supply_chain",
    "Logística y Cadena de Suministro": "logistics_supply_chain",
    "Transportation": "transportation",
    "Transporte": "transportation",
    "Pharmaceutical": "pharmaceutical",
    "Farmacéutica": "pharmaceutical",
    "Construction": "construction",
    "Construcción": "construction",
    "Real Estate": "real_estate",
    "Bienes Raíces": "real_estate",
    "Financial Services": "financial_services",
    "Servicios Financieros": "financial_services",
    "Technology": "technology",
    "Tecnología": "technology",
    "Hospitality": "hospitality",
    "Hospitalidad": "hospitality",
    "Industrial Services": "industrial_services",
    "Servicios Industriales": "industrial_services",
    "Energy": "energy",
    "Energía": "energy",
    "Automotive": "automotive",
    "Automotriz": "automotive",
    "Food and Beverage": "food_beverage",
    "Alimentos y Bebidas": "food_beverage",
    "Professional Services": "professional_services",
    "Servicios Profesionales": "professional_services",
    "Healthcare": "healthcare",
    "Salud": "healthcare",
}

OLD_FUNCTIONAL_AREA_TO_KEY = {
    "General Management": "general_management",
    "Dirección General": "general_management",
    "Operations": "operations",
    "Operaciones": "operations",
    "Manufacturing": "manufacturing",
    "Manufactura": "manufacturing",
    "Supply Chain": "supply_chain",
    "Cadena de Suministro": "supply_chain",
    "Logistics": "logistics",
    "Logística": "logistics",
    "Procurement": "procurement",
    "Compras": "procurement",
    "Sales": "sales",
    "Ventas": "sales",
    "Business Development": "business_development",
    "Desarrollo de Negocio": "business_development",
    "Marketing": "marketing",
    "Finance": "finance",
    "Finanzas": "finance",
    "Accounting": "accounting",
    "Contabilidad": "accounting",
    "Human Resources": "human_resources",
    "Recursos Humanos": "human_resources",
    "Talent Acquisition": "talent_acquisition",
    "Adquisición de Talento": "talent_acquisition",
    "Engineering": "engineering",
    "Ingeniería": "engineering",
    "Quality": "quality",
    "Calidad": "quality",
    "Maintenance": "maintenance",
    "Mantenimiento": "maintenance",
    "IT": "it",
    "Tecnología de la Información": "it",
    "Legal": "legal",
    "Customer Service": "customer_service",
    "Servicio al Cliente": "customer_service",
    "Project Management": "project_management",
    "Gestión de Proyectos": "project_management",
    "Construction Management": "construction_management",
    "Gestión de Construcción": "construction_management",
}


async def migrate_taxonomy():
    """Migrar taxonomía a nuevo esquema con keys canónicas"""
    
    mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    db_name = os.environ.get('ATLAS_DB_NAME') if os.environ.get('ATLAS_URI') else os.environ.get('DB_NAME')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("=" * 60)
    print("  MIGRACIÓN: Taxonomía Bilingüe con Keys Canónicas")
    print("=" * 60)
    
    # 1. Borrar taxonomía existente
    print("\n[1/4] Eliminando taxonomía anterior...")
    await db.industries.delete_many({})
    await db.functional_areas.delete_many({})
    print("   ✓ Taxonomía anterior eliminada")
    
    # 2. Insertar nueva taxonomía desde taxonomy.py
    print("\n[2/4] Insertando nueva taxonomía con keys canónicas...")
    
    from taxonomy import get_all_industries, get_all_functional_areas
    
    industries = []
    for ind in get_all_industries():
        industries.append({
            "id": str(uuid.uuid4()),
            "key": ind["key"],
            "name_es": ind["name_es"],
            "name_en": ind["name_en"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    await db.industries.insert_many(industries)
    print(f"   ✓ {len(industries)} industrias insertadas")
    
    functional_areas = []
    for area in get_all_functional_areas():
        functional_areas.append({
            "id": str(uuid.uuid4()),
            "key": area["key"],
            "name_es": area["name_es"],
            "name_en": area["name_en"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    await db.functional_areas.insert_many(functional_areas)
    print(f"   ✓ {len(functional_areas)} áreas funcionales insertadas")
    
    # 3. Actualizar candidatos existentes
    print("\n[3/4] Actualizando candidatos existentes...")
    
    candidates = await db.candidates.find({}, {"id": 1, "industry": 1, "functional_area": 1}).to_list(None)
    updated_count = 0
    
    for candidate in candidates:
        updates = {}
        
        # Actualizar industry
        old_industry = candidate.get('industry')
        if old_industry and old_industry in OLD_INDUSTRY_TO_KEY:
            updates['industry'] = OLD_INDUSTRY_TO_KEY[old_industry]
        
        # Actualizar functional_area
        old_area = candidate.get('functional_area')
        if old_area and old_area in OLD_FUNCTIONAL_AREA_TO_KEY:
            updates['functional_area'] = OLD_FUNCTIONAL_AREA_TO_KEY[old_area]
        
        if updates:
            await db.candidates.update_one(
                {"id": candidate['id']},
                {"$set": updates}
            )
            updated_count += 1
    
    print(f"   ✓ {updated_count} candidatos actualizados")
    
    # 4. Verificar migración
    print("\n[4/4] Verificando migración...")
    
    industries_count = await db.industries.count_documents({})
    areas_count = await db.functional_areas.count_documents({})
    
    # Mostrar muestra de la nueva taxonomía
    sample_industries = await db.industries.find({}, {"_id": 0, "key": 1, "name_es": 1, "name_en": 1}).limit(5).to_list(5)
    
    print(f"\n   Industrias en DB: {industries_count}")
    print(f"   Áreas funcionales en DB: {areas_count}")
    print("\n   Muestra de industrias:")
    for ind in sample_industries:
        print(f"     - key: {ind['key']}, ES: {ind['name_es']}, EN: {ind['name_en']}")
    
    client.close()
    
    print("\n" + "=" * 60)
    print("  ✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate_taxonomy())
