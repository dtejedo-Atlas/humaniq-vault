#!/usr/bin/env python3
"""
Script de Calibración v2 vs v3 - DOBLE VACANTE
Compara el motor de matching actual (v2) con el nuevo scoring engine (v3).
NO guarda nada en la BD.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, '/app/backend')

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

# Imports
from job_matching_service import JobMatchingService
from embedding_service import EmbeddingService
from scoring.engine_v3 import score_v3
from scoring.config_v3 import COMPONENT_NAMES, WEIGHTS_BY_PROCESS, DEFAULT_PROCESS

COMPONENT_WEIGHTS = WEIGHTS_BY_PROCESS[DEFAULT_PROCESS]


def get_db():
    """Conecta a MongoDB Atlas"""
    mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    client = MongoClient(mongo_url)
    db_name = os.environ.get('DB_NAME', 'humaniq_db')
    return client[db_name]


def find_jobs_for_calibration(db, exclude_area=None):
    """
    Encuentra vacantes para calibración.
    """
    jobs = list(db.jobs.find({"embedding": {"$exists": True, "$ne": None}}))
    
    if not jobs:
        jobs = list(db.jobs.find({}))
    
    if not jobs:
        return []
    
    # Para cada vacante, contar candidatos afines
    job_scores = []
    
    for job in jobs:
        job_area = job.get("functional_area", "")
        
        # Excluir área si se especifica
        if exclude_area and job_area == exclude_area:
            continue
        
        # Contar skills de calidad
        skills = job.get("required_skills", [])
        skill_quality = sum(1 for s in skills if len(s) < 30)
        
        # Contar candidatos afines
        query = {"status": {"$ne": "deleted"}, "is_deleted": {"$ne": True}}
        if job_area:
            query["functional_area"] = job_area
        
        count = db.candidates.count_documents(query)
        combined_score = count + (skill_quality * 5)
        
        job_scores.append((job, combined_score, count, skill_quality, job_area))
    
    # Ordenar por score combinado
    job_scores.sort(key=lambda x: x[1], reverse=True)
    
    return job_scores


def run_v2_matching(db, job, limit=5):
    """
    Ejecuta el motor de matching v2 y devuelve top N candidatos.
    """
    embedding_service = EmbeddingService()
    jms = JobMatchingService(db, embedding_service)
    
    candidates = list(db.candidates.find({
        "status": {"$ne": "deleted"},
        "is_deleted": {"$ne": True},
    }))
    
    job_embedding = job.get("embedding")
    results = []
    
    for candidate in candidates:
        try:
            match_result = jms._calculate_match(candidate, job, job_embedding)
            match_result["candidate_id"] = str(candidate.get("_id"))
            match_result["candidate_name"] = candidate.get("full_name", "N/A")
            match_result["candidate"] = candidate
            match_result["match_score"] = match_result.get("match_percentage", 0)
            results.append(match_result)
        except Exception:
            pass
    
    results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return results[:limit]


def run_v3_scoring(candidates, job):
    """
    Ejecuta score_v3 sobre una lista de candidatos.
    """
    results = []
    for candidate in candidates:
        try:
            result = score_v3(candidate, job)
            results.append(result)
        except Exception as e:
            print(f"   Error v3: {e}")
            results.append(None)
    return results


def print_comparison_table(v2_results, v3_results):
    """Imprime tabla comparativa v2 vs v3."""
    print(f"\n{'#':<3} {'Candidato':<35} {'Score v2':>10} {'HMS v3':>10} {'HEC':>8} {'Acción Recomendada':<25}")
    print("-" * 100)
    
    for i, (v2, v3) in enumerate(zip(v2_results, v3_results), 1):
        name = v2.get("candidate_name", "N/A")[:33]
        score_v2 = v2.get("match_score", 0)
        
        if v3:
            hms_v3 = v3.get("match_score_v3", 0)
            hec = v3.get("confidence_score", 0)
            action = v3.get("recommended_action", "N/A")
        else:
            hms_v3 = "ERR"
            hec = 0
            action = "ERROR"
        
        print(f"{i:<3} {name:<35} {score_v2:>10.1f} {hms_v3:>10} {hec:>8.4f} {action:<25}")
    
    print("-" * 100)


def print_component_breakdown(v3_result):
    """Imprime desglose de 10 componentes del resultado v3."""
    print(f"\nDESGLOSE COMPONENTES: {v3_result.get('candidate_name', 'N/A')}")
    print(f"HMS: {v3_result['match_score_v3']}  |  HEC: {v3_result['confidence_score']:.4f}  |  Acción: {v3_result['recommended_action']}")
    print("-" * 80)
    print(f"{'Código':<6} {'Nombre':<25} {'Raw':>10} {'CI':>10} {'Adjusted':>10}")
    print("-" * 80)
    
    for code in ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"]:
        comp = v3_result["component_breakdown"].get(code, {})
        name = COMPONENT_NAMES.get(code, code)[:23]
        raw = comp.get("raw", 0)
        ci = comp.get("confidence", 0)
        adj = comp.get("adjusted", 0)
        print(f"{code:<6} {name:<25} {raw:>10.4f} {ci:>10.4f} {adj:>10.4f}")
    
    print("-" * 80)
    
    # Estadísticas
    adjusted_values = [v3_result["component_breakdown"].get(c, {}).get("adjusted", 0) 
                       for c in ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"]]
    
    print(f"Promedio adjusted: {sum(adjusted_values)/len(adjusted_values):.4f}")
    print(f"Máximo adjusted: {max(adjusted_values):.4f}")
    print(f"Mínimo adjusted: {min(adjusted_values):.4f}")
    
    # Debug
    debug = v3_result["_debug"]
    print(f"\nA={debug['arithmetic_mean_A']:.4f}, G={debug['geometric_mean_G']:.4f}, Core={debug['core_clamped']:.4f}, K={v3_result['knockout_results']['K']:.4f}")


def run_calibration_for_job(db, job, job_label):
    """Ejecuta calibración completa para una vacante."""
    print("\n" + "=" * 100)
    print(f"CALIBRACIÓN: {job_label}")
    print("=" * 100)
    
    print(f"\nVacante: {job.get('title', 'N/A')}")
    print(f"Área: {job.get('functional_area', 'N/A')}")
    print(f"Industria: {job.get('industry', 'N/A')}")
    print(f"Seniority: {job.get('seniority_level') or job.get('seniority', 'N/A')}")
    print(f"Exp. mínima: {job.get('min_experience', 'N/A')} años")
    print(f"Skills: {job.get('required_skills', [])}")
    
    # v2
    print("\n--- Matching v2 ---")
    v2_results = run_v2_matching(db, job, limit=5)
    
    # v3
    print("--- Scoring v3 ---")
    candidates_for_v3 = [r["candidate"] for r in v2_results]
    v3_results = run_v3_scoring(candidates_for_v3, job)
    
    # Tabla comparativa
    print("\nTABLA COMPARATIVA v2 vs v3:")
    print_comparison_table(v2_results, v3_results)
    
    # Ordenar por HMS v3
    v3_with_v2 = list(zip(v3_results, v2_results))
    v3_with_v2.sort(key=lambda x: x[0]["match_score_v3"] if x[0] else 0, reverse=True)
    
    top_v3 = v3_with_v2[0][0]
    
    # Desglose del #1
    print_component_breakdown(top_v3)
    
    # Resumen
    v3_scores = [r["match_score_v3"] for r in v3_results if r]
    print(f"\nRango HMS v3: {min(v3_scores)} - {max(v3_scores)} (promedio: {sum(v3_scores)/len(v3_scores):.1f})")
    
    return v3_scores


def main():
    print("=" * 100)
    print("CALIBRACIÓN DOBLE - SCORING ENGINE v3")
    print("=" * 100)
    print(f"Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    db = get_db()
    print("✓ Conexión exitosa a MongoDB Atlas")
    
    # Encontrar vacantes
    job_scores = find_jobs_for_calibration(db)
    
    print("\nVacantes disponibles:")
    for job, score, count, sq, area in job_scores[:5]:
        print(f"  - {job.get('title', 'N/A')[:40]}: área={area}, candidatos={count}")
    
    # VACANTE 1: Director Comercial (sales)
    job1 = None
    for job, _, _, _, _ in job_scores:
        if "director comercial" in job.get("title", "").lower():
            job1 = job
            break
    
    if not job1:
        job1 = job_scores[0][0]
    
    scores1 = run_calibration_for_job(db, job1, "VACANTE 1 (Sales)")
    
    # VACANTE 2: Otra área funcional (no sales)
    job2 = None
    for job, _, count, _, area in job_scores:
        if area != "sales" and count >= 5:
            job2 = job
            break
    
    if job2:
        scores2 = run_calibration_for_job(db, job2, "VACANTE 2 (No-Sales)")
    else:
        print("\n⚠ No se encontró vacante de otra área con >=5 candidatos")
        scores2 = []
    
    # Resumen final
    print("\n" + "=" * 100)
    print("RESUMEN FINAL DE DISTRIBUCIÓN HMS")
    print("=" * 100)
    
    all_scores = scores1 + scores2
    
    print(f"\nVacante 1 ({job1.get('functional_area', 'N/A')}): {min(scores1)}-{max(scores1)} (avg: {sum(scores1)/len(scores1):.1f})")
    if scores2:
        print(f"Vacante 2 ({job2.get('functional_area', 'N/A')}): {min(scores2)}-{max(scores2)} (avg: {sum(scores2)/len(scores2):.1f})")
    
    if all_scores:
        print(f"\nDistribución total (n={len(all_scores)}):")
        print(f"  Min: {min(all_scores)}, Max: {max(all_scores)}, Avg: {sum(all_scores)/len(all_scores):.1f}")
        
        # Conteo por rangos de acción
        buckets = {">=85": 0, "75-84": 0, "65-74": 0, "<65": 0}
        for s in all_scores:
            if s >= 85:
                buckets[">=85"] += 1
            elif s >= 75:
                buckets["75-84"] += 1
            elif s >= 65:
                buckets["65-74"] += 1
            else:
                buckets["<65"] += 1
        
        print(f"\nDistribución por rangos:")
        print(f"  >=85 (advance_to_screening): {buckets['>=85']}")
        print(f"  75-84 (review_manually):     {buckets['75-84']}")
        print(f"  65-74 (possible_backup):     {buckets['65-74']}")
        print(f"  <65 (low_priority):          {buckets['<65']}")


if __name__ == "__main__":
    main()
