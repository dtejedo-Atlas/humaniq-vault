"""
Script para regenerar embeddings de candidatos existentes.
Ejecutar después de habilitar OPENAI_API_KEY.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from motor.motor_asyncio import AsyncIOMotorClient
from embedding_service import EmbeddingService

async def regenerate_embeddings():
    """Regenerar embeddings para todos los candidatos sin embedding"""
    
    print("=" * 60)
    print("  REGENERACIÓN DE EMBEDDINGS")
    print("=" * 60)
    
    # Conectar a MongoDB
    mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    db_name = os.environ.get('ATLAS_DB_NAME') if os.environ.get('ATLAS_URI') else os.environ.get('DB_NAME')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Inicializar servicio de embeddings
    embedding_service = EmbeddingService()
    
    if not embedding_service.enabled:
        print("✗ ERROR: Servicio de embeddings no habilitado")
        print("  Verifica que OPENAI_API_KEY está configurada en .env")
        return
    
    print(f"✓ Embedding service habilitado (modelo: {embedding_service.model})")
    
    # Obtener todos los candidatos
    candidates = await db.candidates.find({}, {
        "_id": 0, 
        "id": 1, 
        "full_name": 1, 
        "email": 1,
        "current_title": 1,
        "current_company": 1,
        "skills": 1,
        "industry": 1,
        "functional_area": 1,
        "embedding": 1
    }).to_list(None)
    
    total = len(candidates)
    print(f"\n📊 Candidatos en base de datos: {total}")
    
    # Contar candidatos sin embedding
    without_embedding = [c for c in candidates if not c.get('embedding')]
    with_embedding = [c for c in candidates if c.get('embedding')]
    
    print(f"   - Con embedding: {len(with_embedding)}")
    print(f"   - Sin embedding: {len(without_embedding)}")
    
    if len(without_embedding) == 0:
        print("\n✓ Todos los candidatos ya tienen embedding")
        
        # Aún así, verificar si los embeddings existentes son válidos
        invalid_count = 0
        for c in with_embedding:
            emb = c.get('embedding', [])
            if len(emb) < 100:  # embedding válido debería tener 1536 dimensiones
                invalid_count += 1
        
        if invalid_count > 0:
            print(f"⚠️ {invalid_count} candidatos tienen embeddings inválidos (muy cortos)")
        
        client.close()
        return
    
    print(f"\n🔄 Generando embeddings para {len(without_embedding)} candidatos...")
    print("-" * 60)
    
    success_count = 0
    error_count = 0
    errors = []
    
    for i, candidate in enumerate(without_embedding, 1):
        candidate_id = candidate['id']
        name = candidate.get('full_name', 'Sin nombre')
        
        try:
            # Generar embedding
            embedding = await embedding_service.generate_candidate_embedding(candidate)
            
            if embedding and len(embedding) > 100:
                # Guardar embedding en DB
                await db.candidates.update_one(
                    {"id": candidate_id},
                    {
                        "$set": {
                            "embedding": embedding,
                            "embedding_updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                success_count += 1
                print(f"  [{i}/{len(without_embedding)}] ✓ {name}")
            else:
                error_count += 1
                errors.append({
                    "id": candidate_id,
                    "name": name,
                    "error": "Embedding vacío o inválido"
                })
                print(f"  [{i}/{len(without_embedding)}] ✗ {name} - Embedding inválido")
                
        except Exception as e:
            error_count += 1
            errors.append({
                "id": candidate_id,
                "name": name,
                "error": str(e)
            })
            print(f"  [{i}/{len(without_embedding)}] ✗ {name} - Error: {str(e)[:50]}")
        
        # Pequeña pausa para no saturar la API
        await asyncio.sleep(0.5)
    
    print("-" * 60)
    print(f"\n📊 RESUMEN DE REGENERACIÓN:")
    print(f"   ✓ Exitosos: {success_count}")
    print(f"   ✗ Fallidos: {error_count}")
    
    if errors:
        print(f"\n⚠️ Candidatos con errores:")
        for err in errors:
            print(f"   - {err['name']}: {err['error'][:60]}")
    
    # Verificar estado final
    final_count = await db.candidates.count_documents({"embedding": {"$exists": True, "$ne": None, "$not": {"$size": 0}}})
    print(f"\n✓ Candidatos con embedding válido: {final_count}/{total}")
    
    client.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(regenerate_embeddings())
