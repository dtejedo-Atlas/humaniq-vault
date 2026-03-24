"""
Script de migración para agregar campos normalizados a candidatos existentes.

Ejecutar UNA VEZ después del deploy.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from pathlib import Path
from dotenv import load_dotenv
from text_utils import normalize_for_search

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

async def migrate_candidates():
    """Agregar campos normalizados a todos los candidatos existentes"""
    
    # Connect to MongoDB
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ['DB_NAME']]
    
    print("🔄 Iniciando migración de candidatos existentes...")
    
    # Get all candidates
    candidates = await db.candidates.find({}, {"_id": 0}).to_list(10000)
    
    total = len(candidates)
    print(f"📊 Total de candidatos a migrar: {total}")
    
    if total == 0:
        print("✅ No hay candidatos para migrar")
        return
    
    updated = 0
    errors = 0
    
    for candidate in candidates:
        try:
            candidate_id = candidate.get('id')
            
            # Generar campos normalizados
            updates = {}
            
            if full_name := candidate.get('full_name'):
                updates['full_name_normalized'] = normalize_for_search(full_name)
            
            if company := candidate.get('current_company'):
                updates['company_normalized'] = normalize_for_search(company)
            
            if title := candidate.get('current_title'):
                updates['title_normalized'] = normalize_for_search(title)
            
            # Update in database
            if updates:
                await db.candidates.update_one(
                    {"id": candidate_id},
                    {"$set": updates}
                )
                updated += 1
                
                if updated % 10 == 0:
                    print(f"   Procesados: {updated}/{total}")
        
        except Exception as e:
            print(f"❌ Error en candidato {candidate.get('id')}: {str(e)}")
            errors += 1
    
    print(f"\n✅ Migración completada:")
    print(f"   - Actualizados: {updated}")
    print(f"   - Errores: {errors}")
    print(f"   - Total: {total}")
    
    # Verificar resultados
    sample = await db.candidates.find_one(
        {"full_name_normalized": {"$exists": True}},
        {"_id": 0, "full_name": 1, "full_name_normalized": 1}
    )
    
    if sample:
        print(f"\n📋 Ejemplo de migración:")
        print(f"   Original: {sample.get('full_name')}")
        print(f"   Normalizado: {sample.get('full_name_normalized')}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_candidates())
