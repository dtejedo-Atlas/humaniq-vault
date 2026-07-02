#!/usr/bin/env python3
"""
Scoring Engine v3 - Dry Run Script
Evalúa 3 candidatos reales vs 1 vacante real desde MongoDB Atlas.
NO guarda nada en la BD, solo muestra el resultado.
"""
import os
import sys
from datetime import datetime, timezone

# Añadir path
sys.path.insert(0, '/app/backend')

from pymongo import MongoClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Import del motor v3
from scoring.engine_v3 import score_v3, format_score_report


def get_db_connection():
    """Conecta a MongoDB Atlas"""
    mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("No se encontró ATLAS_URI ni MONGO_URL en el entorno")
    
    client = MongoClient(mongo_url)
    db_name = os.environ.get('DB_NAME', 'humaniq_db')
    return client[db_name]


def fetch_active_candidates(db, limit=3):
    """
    Obtiene candidatos activos con datos suficientes para el scoring.
    Prioriza candidatos con embeddings y datos completos.
    """
    query = {
        "status": {"$ne": "deleted"},
        "embedding": {"$exists": True, "$not": {"$in": [None, []]}},
        "skills": {"$exists": True, "$not": {"$size": 0}},
    }
    
    projection = {
        "_id": 1,
        "full_name": 1,
        "email": 1,
        "phone": 1,
        "current_title": 1,
        "current_company": 1,
        "years_experience": 1,
        "industry": 1,
        "functional_area": 1,
        "seniority": 1,
        "city": 1,
        "state": 1,
        "skills": 1,
        "languages": 1,
        "previous_companies": 1,
        "embedding": 1,
        "ai_classification": 1,
        "resume_files": 1,
        "created_at": 1,
        "updated_at": 1,
    }
    
    candidates = list(db.candidates.find(query, projection).limit(limit))
    
    # Convertir _id a string para el output
    for c in candidates:
        c["id"] = str(c["_id"])
    
    return candidates


def fetch_active_job(db):
    """
    Obtiene una vacante activa con datos suficientes para el scoring.
    """
    query = {
        "status": {"$in": ["active", "abierta", None]},
    }
    
    projection = {
        "_id": 1,
        "title": 1,
        "functional_area": 1,
        "industry": 1,
        "seniority_level": 1,
        "seniority": 1,
        "min_experience": 1,
        "city": 1,
        "state": 1,
        "work_scheme": 1,
        "required_languages": 1,
        "required_skills": 1,
        "preferred_skills": 1,
        "embedding": 1,
    }
    
    job = db.jobs.find_one(query, projection)
    
    if job:
        job["id"] = str(job["_id"])
    
    return job


def print_candidate_summary(candidate):
    """Imprime resumen breve del candidato"""
    print(f"\n  📋 {candidate.get('full_name', 'N/A')}")
    print(f"     Título: {candidate.get('current_title', 'N/A')}")
    print(f"     Industria: {candidate.get('industry', 'N/A')}")
    print(f"     Área: {candidate.get('functional_area', 'N/A')}")
    print(f"     Seniority: {candidate.get('seniority', 'N/A')}")
    print(f"     Experiencia: {candidate.get('years_experience', 'N/A')} años")
    print(f"     Skills: {len(candidate.get('skills', []))} items")
    print(f"     Embedding: {'✓' if candidate.get('embedding') else '✗'}")


def print_job_summary(job):
    """Imprime resumen breve de la vacante"""
    print(f"\n  📌 {job.get('title', 'N/A')}")
    print(f"     Industria: {job.get('industry', 'N/A')}")
    print(f"     Área: {job.get('functional_area', 'N/A')}")
    print(f"     Seniority: {job.get('seniority_level') or job.get('seniority', 'N/A')}")
    print(f"     Exp. mínima: {job.get('min_experience', 'N/A')} años")
    print(f"     Ubicación: {job.get('city', 'N/A')}, {job.get('state', 'N/A')}")
    print(f"     Esquema: {job.get('work_scheme', 'N/A')}")
    print(f"     Skills requeridos: {len(job.get('required_skills', []))} items")
    print(f"     Idiomas requeridos: {job.get('required_languages', [])}")


def print_full_result(result):
    """Imprime el resultado completo del scoring"""
    print(format_score_report(result))


def print_component_table(result):
    """Imprime tabla de componentes"""
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │                    COMPONENTES (10)                         │")
    print("  ├──────┬─────────────────────────┬────────┬────────┬──────────┤")
    print("  │ Código│ Nombre                  │ Raw    │ CI     │ Adjusted │")
    print("  ├──────┼─────────────────────────┼────────┼────────┼──────────┤")
    
    from scoring.config_v3 import COMPONENT_NAMES
    
    for code in ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"]:
        comp = result["component_breakdown"].get(code, {})
        name = COMPONENT_NAMES.get(code, code)[:23]
        raw = comp.get("raw", 0)
        ci = comp.get("confidence", 0)
        adj = comp.get("adjusted", 0)
        print(f"  │ {code:<4} │ {name:<23} │ {raw:>6.4f} │ {ci:>6.4f} │ {adj:>8.4f} │")
    
    print("  └──────┴─────────────────────────┴────────┴────────┴──────────┘")


def print_hec_table(result):
    """Imprime tabla de señales HEC"""
    print("  ┌───────────────────────────────────────────────────────────┐")
    hec_display = f"HEC (Confidence): {result['confidence_score']:.4f}"
    print(f"  │ {hec_display:<57} │")
    print("  ├────────┬────────┬──────────┬──────────────────────────────┤")
    print("  │ Señal  │ Score  │ Peso     │ Descripción                  │")
    print("  ├────────┼────────┼──────────┼──────────────────────────────┤")
    
    for signal in ["EC", "PC", "HV", "DC", "CV", "RC"]:
        data = result["hec_breakdown"].get(signal, {})
        score = data.get("score", 0)
        weight = data.get("weight", 0)
        desc = data.get("description", "")[:28]
        print(f"  │ {signal:<6} │ {score:>6.4f} │ {weight:>8.2f} │ {desc:<28} │")
    
    print("  └────────┴────────┴──────────┴──────────────────────────────┘")


def print_knockouts(result):
    """Imprime resultados de knockouts"""
    kr = result["knockout_results"]
    print(f"\n  KNOCKOUTS (K = {kr['K']:.4f}):")
    
    for k in kr["results"]:
        status_icon = "✓" if k["status"] == "cumple" else ("⚠" if k["status"] == "parcial" else "✗")
        print(f"    {status_icon} {k['evaluator']}: {k['status']} ({k['value']:.2f})")
        if k.get("note"):
            print(f"      └─ {k['note'][:60]}")


def print_boosts_penalties(result):
    """Imprime boosts y penalties"""
    print(f"\n  BOOSTS: {result['boosts']['total']:.4f} (cap: {result['boosts']['cap']})")
    for b in result["boosts"]["applied"]:
        print(f"    + {b['name']}: +{b['value']:.3f}")
    if not result["boosts"]["applied"]:
        print("    (ninguno)")
    
    print(f"\n  PENALTIES: {result['penalties']['total']:.4f} (cap: {result['penalties']['cap']})")
    for p in result["penalties"]["applied"]:
        print(f"    - {p['name']}: -{p['value']:.3f}")
    if not result["penalties"]["applied"]:
        print("    (ninguna)")


def main():
    print("=" * 70)
    print("HUMANIQ TALENT VAULT - SCORING ENGINE v3 DRY RUN")
    print("=" * 70)
    print(f"Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Conectar a la BD
    print("\n🔌 Conectando a MongoDB Atlas...")
    try:
        db = get_db_connection()
        print("   ✓ Conexión exitosa")
    except Exception as e:
        print(f"   ✗ Error de conexión: {e}")
        return
    
    # Obtener vacante
    print("\n📌 Buscando vacante activa...")
    job = fetch_active_job(db)
    
    if not job:
        print("   ✗ No se encontraron vacantes activas")
        return
    
    print_job_summary(job)
    
    # Obtener candidatos
    print("\n\n👥 Buscando 3 candidatos activos con embeddings...")
    candidates = fetch_active_candidates(db, limit=3)
    
    if not candidates:
        print("   ✗ No se encontraron candidatos con embeddings")
        return
    
    print(f"   ✓ Encontrados {len(candidates)} candidatos")
    
    for c in candidates:
        print_candidate_summary(c)
    
    # Ejecutar scoring
    print("\n\n" + "=" * 70)
    print("RESULTADOS DEL SCORING")
    print("=" * 70)
    
    for i, candidate in enumerate(candidates, 1):
        print(f"\n\n{'─' * 70}")
        print(f"CANDIDATO {i}: {candidate.get('full_name', 'N/A')}")
        print(f"{'─' * 70}")
        
        try:
            result = score_v3(candidate, job)
            
            # Header con HMS y acción
            print("\n  ╔══════════════════════════════════════════════════════════════╗")
            print(f"  ║ HMS: {result['match_score_v3']:>3}  │  HEC: {result['confidence_score']:.4f}  │  Acción: {result['recommended_action']:<20} ║")
            print("  ╚══════════════════════════════════════════════════════════════╝")
            
            # Tabla de componentes
            print_component_table(result)
            
            # Tabla de HEC
            print_hec_table(result)
            
            # Knockouts
            print_knockouts(result)
            
            # Boosts y Penalties
            print_boosts_penalties(result)
            
            # Debug info
            print("\n  DEBUG:")
            print(f"    A (aritmética): {result['_debug']['arithmetic_mean_A']:.4f}")
            print(f"    G (geométrica): {result['_debug']['geometric_mean_G']:.4f}")
            print(f"    Core (raw):     {result['_debug']['core_raw']:.4f}")
            print(f"    Core (clamped): {result['_debug']['core_clamped']:.4f}")
            print(f"    HMS raw:        {result['_debug']['hms_raw']:.4f}")
            
        except Exception as e:
            print(f"\n  ✗ Error al procesar: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n\n" + "=" * 70)
    print("FIN DEL DRY RUN")
    print("=" * 70)
    print("\n✓ NO se guardó nada en la base de datos")


if __name__ == "__main__":
    main()
