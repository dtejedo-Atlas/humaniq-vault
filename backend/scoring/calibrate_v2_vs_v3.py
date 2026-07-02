#!/usr/bin/env python3
"""
Script de Calibración v2 vs v3
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
from scoring.config_v3 import COMPONENT_NAMES, COMPONENT_WEIGHTS


def get_db():
    """Conecta a MongoDB Atlas"""
    mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    client = MongoClient(mongo_url)
    db_name = os.environ.get('DB_NAME', 'humaniq_db')
    return client[db_name]


def find_best_job_for_calibration(db):
    """
    Encuentra la vacante con más candidatos afines.
    Prioriza vacantes con skills bien definidos (cortos, no frases largas).
    """
    jobs = list(db.jobs.find({"embedding": {"$exists": True, "$ne": None}}))
    
    if not jobs:
        jobs = list(db.jobs.find({}))
    
    if not jobs:
        return None
    
    # Priorizar vacantes con skills bien definidos
    job_scores = []
    
    for job in jobs:
        skills = job.get("required_skills", [])
        
        # Calcular calidad de skills (penalizar frases largas)
        skill_quality = 0
        for s in skills:
            if len(s) < 30:  # Skills cortos son mejores
                skill_quality += 1
        
        job_area = job.get("functional_area", "")
        
        # Contar candidatos afines
        query = {
            "status": {"$ne": "deleted"},
            "is_deleted": {"$ne": True},
        }
        
        if job_area:
            query["functional_area"] = job_area
        
        count = db.candidates.count_documents(query)
        
        # Score combinado: candidatos afines + calidad de skills
        combined_score = count + (skill_quality * 5)
        
        job_scores.append((job, combined_score, count, skill_quality))
    
    # Ordenar por score combinado
    job_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Mostrar las opciones
    print("\n   Candidatos por vacante:")
    for job, score, count, sq in job_scores[:3]:
        print(f"     - {job.get('title', 'N/A')[:40]}: {count} candidatos afines, skill_quality={sq}")
    
    return job_scores[0][0] if job_scores else None


def run_v2_matching(db, job, limit=5):
    """
    Ejecuta el motor de matching v2 y devuelve top N candidatos.
    """
    embedding_service = EmbeddingService()
    jms = JobMatchingService(db, embedding_service)
    
    # Obtener candidatos activos
    candidates = list(db.candidates.find({
        "status": {"$ne": "deleted"},
        "is_deleted": {"$ne": True},
    }))
    
    print(f"   Total candidatos activos: {len(candidates)}")
    
    # Obtener o generar embedding de la vacante
    job_embedding = job.get("embedding")
    
    results = []
    
    for candidate in candidates:
        try:
            match_result = jms._calculate_match(candidate, job, job_embedding)
            
            # Añadir info del candidato
            match_result["candidate_id"] = str(candidate.get("_id"))
            match_result["candidate_name"] = candidate.get("full_name", "N/A")
            match_result["candidate"] = candidate
            match_result["match_score"] = match_result.get("match_percentage", 0)  # Alias
            
            results.append(match_result)
        except Exception as e:
            print(f"   Error procesando {candidate.get('full_name')}: {e}")
    
    # Ordenar por score total (match_score)
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
            print(f"   Error v3 para {candidate.get('full_name')}: {e}")
            results.append(None)
    
    return results


def print_comparison_table(v2_results, v3_results):
    """
    Imprime tabla comparativa v2 vs v3.
    """
    print("\n" + "=" * 100)
    print("TABLA COMPARATIVA: v2 vs v3")
    print("=" * 100)
    print(f"{'#':<3} {'Candidato':<35} {'Score v2':>10} {'HMS v3':>10} {'HEC':>8} {'Acción Recomendada':<25}")
    print("-" * 100)
    
    for i, (v2, v3) in enumerate(zip(v2_results, v3_results), 1):
        name = v2.get("candidate_name", "N/A")[:33]
        score_v2 = v2.get("match_score", 0)
        
        if v3:
            hms_v3 = v3.get("match_score_v3", 0)
            hec = v3.get("confidence_score", 0)
            action = v3.get("recommended_action", "N/A")
        else:
            hms_v3 = "ERROR"
            hec = "N/A"
            action = "ERROR"
        
        print(f"{i:<3} {name:<35} {score_v2:>10.1f} {hms_v3:>10} {hec:>8.4f} {action:<25}")
    
    print("-" * 100)


def print_full_breakdown(v3_result):
    """
    Imprime el desglose completo del candidato #1 en v3.
    """
    print("\n" + "=" * 100)
    print(f"DESGLOSE COMPLETO: {v3_result.get('candidate_name', 'N/A')}")
    print("=" * 100)
    
    # Header
    print(f"\nHMS: {v3_result['match_score_v3']}  |  HEC: {v3_result['confidence_score']:.4f}  |  Acción: {v3_result['recommended_action']}")
    
    # 1. Componentes
    print("\n" + "-" * 80)
    print("10 COMPONENTES")
    print("-" * 80)
    print(f"{'Código':<6} {'Nombre':<25} {'Raw':>10} {'CI':>10} {'Adjusted':>10} {'Peso':>8}")
    print("-" * 80)
    
    adjusted_values = []
    
    for code in ["SK", "ER", "FA", "SA", "IA", "ED", "TR", "LO", "SM", "CQ"]:
        comp = v3_result["component_breakdown"].get(code, {})
        name = COMPONENT_NAMES.get(code, code)[:23]
        raw = comp.get("raw", 0)
        ci = comp.get("confidence", 0)
        adj = comp.get("adjusted", 0)
        weight = COMPONENT_WEIGHTS.get(code, 0)
        
        adjusted_values.append(adj)
        
        print(f"{code:<6} {name:<25} {raw:>10.4f} {ci:>10.4f} {adj:>10.4f} {weight:>8.2f}")
    
    print("-" * 80)
    
    # 2. Señales HEC
    print("\n" + "-" * 80)
    print("6 SEÑALES HEC")
    print("-" * 80)
    print(f"{'Señal':<8} {'Score':>10} {'Peso':>10} {'Weighted':>10} {'Descripción':<35}")
    print("-" * 80)
    
    for signal in ["EC", "PC", "HV", "DC", "CV", "RC"]:
        data = v3_result["hec_breakdown"].get(signal, {})
        score = data.get("score", 0)
        weight = data.get("weight", 0)
        weighted = data.get("weighted", 0)
        desc = data.get("description", "")[:33]
        
        print(f"{signal:<8} {score:>10.4f} {weight:>10.2f} {weighted:>10.4f} {desc:<35}")
    
    print("-" * 80)
    
    # 3. Knockouts
    print("\n" + "-" * 80)
    print(f"KNOCKOUTS (K = {v3_result['knockout_results']['K']:.4f})")
    print("-" * 80)
    
    for ko in v3_result["knockout_results"]["results"]:
        criterion = ko.get("criterion", ko.get("evaluator", "N/A"))
        k_value = ko.get("k_value")
        status = ko.get("status", "N/A")
        
        if status == "no_aplica" or k_value is None:
            icon = "○"
            k_str = "N/A"
        elif status == "cumple":
            icon = "✓"
            k_str = f"{k_value:.2f}"
        elif status in ["parcial", "evidencia_insuficiente"]:
            icon = "⚠"
            k_str = f"{k_value:.2f}"
        else:
            icon = "✗"
            k_str = f"{k_value:.2f}"
        
        print(f"  {icon} {criterion:<15}: {status:<25} (k={k_str})")
        if ko.get("note"):
            print(f"                     └─ {ko['note'][:60]}")
    
    # 4. Boosts
    print("\n" + "-" * 80)
    print(f"BOOSTS (total: {v3_result['boosts']['total']:.4f}, cap: {v3_result['boosts']['cap']})")
    print("-" * 80)
    
    if v3_result["boosts"]["applied"]:
        for b in v3_result["boosts"]["applied"]:
            print(f"  + {b['name']}: +{b['value']:.3f} - {b['reason']}")
    else:
        print("  (ninguno aplicado)")
    
    # 5. Penalties
    print("\n" + "-" * 80)
    print(f"PENALTIES (total: {v3_result['penalties']['total']:.4f}, cap: {v3_result['penalties']['cap']})")
    print("-" * 80)
    
    if v3_result["penalties"]["applied"]:
        for p in v3_result["penalties"]["applied"]:
            print(f"  - {p['name']}: -{p['value']:.3f} - {p['reason']}")
    else:
        print("  (ninguna aplicada)")
    
    # 6. Estadísticas de adjusted
    print("\n" + "-" * 80)
    print("ESTADÍSTICAS DE COMPONENTES ADJUSTED")
    print("-" * 80)
    
    avg_adjusted = sum(adjusted_values) / len(adjusted_values)
    max_adjusted = max(adjusted_values)
    min_adjusted = min(adjusted_values)
    
    print(f"  Promedio de adjusted: {avg_adjusted:.4f}")
    print(f"  Máximo adjusted:      {max_adjusted:.4f}")
    print(f"  Mínimo adjusted:      {min_adjusted:.4f}")
    
    # 7. Debug info
    print("\n" + "-" * 80)
    print("DEBUG - CÁLCULO INTERNO")
    print("-" * 80)
    debug = v3_result["_debug"]
    print(f"  A (media aritmética): {debug['arithmetic_mean_A']:.4f}")
    print(f"  G (media geométrica): {debug['geometric_mean_G']:.4f}")
    print(f"  Boosts:               +{v3_result['boosts']['total']:.4f}")
    print(f"  Penalties:            -{v3_result['penalties']['total']:.4f}")
    print(f"  Core raw:             {debug['core_raw']:.4f}")
    print(f"  Core (clamped):       {debug['core_clamped']:.4f}")
    print(f"  K (knockout):         {v3_result['knockout_results']['K']:.4f}")
    print(f"  HEC^0.15:             {debug['hec_factor']:.4f}")
    print(f"  HMS raw:              {debug['hms_raw']:.4f}")
    print(f"  HMS final:            {v3_result['match_score_v3']}")
    
    print("\n" + "=" * 100)
    
    return avg_adjusted, max_adjusted


def main():
    print("=" * 100)
    print("CALIBRACIÓN DEL SCORING ENGINE v3")
    print("=" * 100)
    print(f"Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Conectar
    print("\n🔌 Conectando a MongoDB Atlas...")
    db = get_db()
    print("   ✓ Conexión exitosa")
    
    # 1. Encontrar mejor vacante
    print("\n📌 Buscando vacante con más candidatos afines...")
    job = find_best_job_for_calibration(db)
    
    if not job:
        print("   ✗ No se encontraron vacantes")
        return
    
    print(f"\n   VACANTE SELECCIONADA:")
    print(f"   Título: {job.get('title', 'N/A')}")
    print(f"   Área: {job.get('functional_area', 'N/A')}")
    print(f"   Industria: {job.get('industry', 'N/A')}")
    print(f"   Seniority: {job.get('seniority_level') or job.get('seniority', 'N/A')}")
    print(f"   Exp. mínima: {job.get('min_experience', 'N/A')} años")
    print(f"   Skills requeridos: {job.get('required_skills', [])}")
    print(f"   Idiomas: {job.get('required_languages', [])}")
    print(f"   Embedding: {'✓' if job.get('embedding') else '✗'}")
    
    # 2. Correr matching v2
    print("\n" + "=" * 100)
    print("PASO 1: MATCHING v2 (motor actual)")
    print("=" * 100)
    
    v2_results = run_v2_matching(db, job, limit=5)
    
    print(f"\n   TOP 5 por v2:")
    for i, r in enumerate(v2_results, 1):
        print(f"   {i}. {r['candidate_name'][:40]:<40} Score: {r['match_score']:.1f}")
    
    # 3. Extraer candidatos para v3
    candidates_for_v3 = [r["candidate"] for r in v2_results]
    
    # 4. Correr scoring v3
    print("\n" + "=" * 100)
    print("PASO 2: SCORING v3 (nuevo motor)")
    print("=" * 100)
    
    v3_results = run_v3_scoring(candidates_for_v3, job)
    
    # 5. Tabla comparativa
    print_comparison_table(v2_results, v3_results)
    
    # 6. Desglose del #1 y #5 en v3
    # Ordenar v3_results por HMS
    v3_with_v2 = list(zip(v3_results, v2_results))
    v3_with_v2.sort(key=lambda x: x[0]["match_score_v3"] if x[0] else 0, reverse=True)
    
    top_v3 = v3_with_v2[0][0]
    bottom_v3 = v3_with_v2[-1][0] if len(v3_with_v2) >= 5 else v3_with_v2[-1][0]
    
    print("\n" + "=" * 100)
    print("PASO 3: DESGLOSE DEL CANDIDATO #1 EN v3")
    print("=" * 100)
    
    avg_adj_1, max_adj_1 = print_full_breakdown(top_v3)
    
    print("\n" + "=" * 100)
    print("PASO 4: DESGLOSE DEL CANDIDATO #5 EN v3")
    print("=" * 100)
    
    avg_adj_5, max_adj_5 = print_full_breakdown(bottom_v3)
    
    # Resumen final
    print("\n" + "=" * 100)
    print("RESUMEN DE CALIBRACIÓN")
    print("=" * 100)
    
    v2_scores = [r["match_score"] for r in v2_results]
    v3_scores = [r["match_score_v3"] for r in v3_results if r]
    
    print(f"\n  Vacante: {job.get('title', 'N/A')}")
    print(f"\n  v2 (motor actual):")
    print(f"    - Rango de scores: {min(v2_scores):.1f} - {max(v2_scores):.1f}")
    print(f"    - Promedio top 5: {sum(v2_scores)/len(v2_scores):.1f}")
    
    print(f"\n  v3 (nuevo motor):")
    print(f"    - Rango de HMS: {min(v3_scores)} - {max(v3_scores)}")
    print(f"    - Promedio top 5: {sum(v3_scores)/len(v3_scores):.1f}")
    
    print(f"\n  Candidato #1 v3 ({top_v3['candidate_name']}):")
    print(f"    - Promedio adjusted: {avg_adj_1:.4f}")
    print(f"    - Máximo adjusted: {max_adj_1:.4f}")
    
    print(f"\n  Candidato #5 v3 ({bottom_v3['candidate_name']}):")
    print(f"    - Promedio adjusted: {avg_adj_5:.4f}")
    print(f"    - Máximo adjusted: {max_adj_5:.4f}")
    
    print("\n" + "=" * 100)
    print("FIN DE CALIBRACIÓN")
    print("=" * 100)


if __name__ == "__main__":
    main()
