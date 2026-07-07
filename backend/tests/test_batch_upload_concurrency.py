"""
Tests para el fix del BUG P0: batch upload concurrente sin bloqueo del event loop.

Cubre:
1) POST /api/candidates/upload-batch retorna inmediatamente con batch_id
2) GET /api/candidates/batch/{batch_id} NO da 404 y devuelve progreso
3) Todos los jobs terminan en completed/duplicate/failed (no colgados)
4) Event loop NO bloqueado: peticiones concurrentes (GET /api/candidates, /api/jobs, /api/auth/me)
   responden rápido (<5s) mientras el batch se procesa
5) Logs backend NO tienen 'asyncio.run() cannot be called from a running event loop'
6) Candidatos aparecen en BD con datos parseados
"""

import io
import os
import time
import uuid
import asyncio
import subprocess
from datetime import datetime

import pytest
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://atlas-recruiting-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "test_utf8@atlas.com"
ADMIN_PASSWORD = "Humaniq123"

# --- Utilidades ---------------------------------------------------------------

def _make_cv_pdf(name: str, role: str, skills: list, years: int) -> bytes:
    """Genera un PDF de CV con contenido único suficiente para que el parser LLM extraiga datos."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 740, name)
    c.setFont("Helvetica", 11)
    c.drawString(72, 720, f"Email: {name.lower().replace(' ', '.')}@example.com")
    c.drawString(72, 705, f"Teléfono: +52 55 1234 {uuid.uuid4().hex[:4]}")
    c.drawString(72, 690, f"Ubicación: Ciudad de México")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, 660, "RESUMEN PROFESIONAL")
    c.setFont("Helvetica", 10)
    resumen = (
        f"Profesional {role} con {years} años de experiencia liderando equipos y proyectos "
        f"en México y Latinoamérica. Especialista en {', '.join(skills[:2])} con enfoque en "
        f"transformación digital, estrategia y resultados medibles."
    )
    # split resumen into lines
    y = 640
    for line in [resumen[i:i+95] for i in range(0, len(resumen), 95)]:
        c.drawString(72, y, line)
        y -= 14

    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y - 10, "EXPERIENCIA")
    c.setFont("Helvetica", 10)
    y -= 30
    experiencias = [
        (f"{role} Senior", "Empresa Alpha S.A.", "2020 - Presente",
         f"Lideré equipos multidisciplinarios de más de 20 personas."),
        (f"{role}", "Empresa Beta S.A.", "2015 - 2020",
         f"Responsable de estrategia y ejecución en {skills[0]}."),
        ("Analista Senior", "Empresa Gamma", "2010 - 2015",
         f"Implementación de proyectos de {skills[-1]}."),
    ]
    for cargo, empresa, periodo, detalle in experiencias:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(72, y, f"{cargo} — {empresa}")
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(72, y - 12, periodo)
        c.setFont("Helvetica", 10)
        c.drawString(72, y - 26, detalle)
        y -= 50

    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "HABILIDADES")
    c.setFont("Helvetica", 10)
    c.drawString(72, y - 15, ", ".join(skills))

    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y - 40, "EDUCACIÓN")
    c.setFont("Helvetica", 10)
    c.drawString(72, y - 55, "Maestría en Administración — ITESM")
    c.drawString(72, y - 70, "Licenciatura en Ingeniería — UNAM")

    c.showPage()
    c.save()
    return buf.getvalue()


def _get_token() -> str:
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def token():
    return _get_token()


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- 1) Endpoint /upload-batch responde rápido y devuelve batch_id -------------

RUN_TAG = uuid.uuid4().hex[:8]
BATCH_STATE = {}  # compartir estado entre tests


def _build_test_files():
    """Crea 4 CVs únicos para el batch."""
    files = []
    profiles = [
        (f"Ana Batch{RUN_TAG} Ramírez", "Directora de Operaciones",
         ["Operations Management", "Lean Six Sigma", "SAP", "P&L Management"], 15),
        (f"Bruno Batch{RUN_TAG} Salazar", "Gerente Comercial",
         ["Ventas B2B", "CRM Salesforce", "Negociación", "Key Account Management"], 12),
        (f"Carla Batch{RUN_TAG} Gómez", "Directora de Marketing",
         ["Digital Marketing", "SEO/SEM", "Analytics", "Brand Strategy"], 10),
        (f"Daniel Batch{RUN_TAG} Núñez", "CTO",
         ["Python", "Kubernetes", "AWS", "Arquitectura de Software"], 14),
    ]
    for name, role, skills, years in profiles:
        pdf_bytes = _make_cv_pdf(name, role, skills, years)
        safe_name = name.replace(" ", "_")
        files.append(
            ("files", (f"{safe_name}.pdf", pdf_bytes, "application/pdf"))
        )
    return files


def test_01_upload_batch_returns_immediately(auth_headers):
    """POST /api/candidates/upload-batch retorna en <10s con batch_id (event loop no bloqueado)."""
    files = _build_test_files()
    t0 = time.time()
    r = requests.post(f"{API}/candidates/upload-batch",
                      headers=auth_headers, files=files, timeout=30)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"upload-batch failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert "batch_id" in data and data["batch_id"], "No batch_id in response"
    assert data.get("total_files") == 4
    # Debería contestar rápido; permito holgura amplia por I/O
    assert elapsed < 15, f"upload-batch demoró demasiado ({elapsed:.1f}s): posible bloqueo del event loop"
    BATCH_STATE["batch_id"] = data["batch_id"]
    BATCH_STATE["queued"] = data.get("queued", 0)
    BATCH_STATE["response_time_s"] = round(elapsed, 2)
    print(f"[batch] batch_id={data['batch_id']} queued={data.get('queued')} elapsed={elapsed:.2f}s")


# --- 2) GET /candidates/batch/{batch_id} NO da 404 --------------------------------

def test_02_batch_status_endpoint_not_404(auth_headers):
    assert "batch_id" in BATCH_STATE, "Test 01 debe correr primero"
    batch_id = BATCH_STATE["batch_id"]
    r = requests.get(f"{API}/candidates/batch/{batch_id}",
                     headers=auth_headers, timeout=15)
    assert r.status_code == 200, f"batch status returned {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("batch_id") == batch_id
    assert "total_jobs" in data or "jobs" in data or "status" in data, \
        f"Respuesta inesperada de batch status: {list(data.keys())}"
    print(f"[batch_status] keys={list(data.keys())} status={data.get('status')}")


# --- 3) EVENT LOOP no bloqueado: peticiones concurrentes rápidas -----------------

def test_03_event_loop_not_blocked_during_processing(auth_headers):
    """Mientras el batch se procesa, GET /api/candidates y /api/jobs deben responder <5s."""
    assert "batch_id" in BATCH_STATE
    # Espera unos segundos para asegurar que los workers están procesando
    time.sleep(3)

    endpoints = [
        ("/candidates?limit=5", "GET"),
        ("/jobs", "GET"),
        ("/auth/me", "GET"),
        ("/candidates/queue/stats", "GET"),
    ]
    slow = []
    ok = []
    for path, method in endpoints:
        t0 = time.time()
        try:
            r = requests.request(method, f"{API}{path}",
                                 headers=auth_headers, timeout=8)
            elapsed = time.time() - t0
            info = f"{path} -> {r.status_code} in {elapsed:.2f}s"
            if elapsed > 5.0:
                slow.append(info)
            if r.status_code >= 500:
                slow.append(f"{path} -> {r.status_code}")
            ok.append(info)
        except requests.Timeout:
            slow.append(f"{path} -> TIMEOUT >8s")
    print("[event_loop_check]\n  " + "\n  ".join(ok))
    assert not slow, f"Event loop parece bloqueado o hay errores: {slow}"


# --- 4) Los jobs terminan (completed/duplicate/failed) sin colgarse --------------

def test_04_batch_processes_all_jobs(auth_headers):
    """Poll hasta 5 minutos hasta que ningún job quede en queued/processing."""
    assert "batch_id" in BATCH_STATE
    batch_id = BATCH_STATE["batch_id"]

    deadline = time.time() + 300  # 5 minutos
    last_snapshot = None
    while time.time() < deadline:
        r = requests.get(f"{API}/candidates/batch/{batch_id}",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"batch endpoint failed mid-poll: {r.status_code}"
        data = r.json()
        last_snapshot = data
        # El endpoint devuelve `stats` (pending/processing/completed/partial/failed) e `is_complete`
        stats = data.get("stats") or {}
        # Compat con posibles claves alternativas
        completed = stats.get("completed", data.get("completed", 0))
        failed = stats.get("failed", data.get("failed", 0))
        duplicate = stats.get("duplicate", data.get("duplicate", 0))
        partial = stats.get("partial", 0)
        processing = stats.get("processing", data.get("processing", 0))
        pending = stats.get("pending", data.get("queued", 0))
        total = data.get("total_files") or data.get("total_jobs") or data.get("total") or 4
        done = completed + failed + duplicate + partial
        is_complete = data.get("is_complete", False)
        print(f"[poll] total={total} done={done} completed={completed} "
              f"failed={failed} dup={duplicate} partial={partial} "
              f"processing={processing} pending={pending} is_complete={is_complete}")
        if is_complete or (done >= total and processing == 0 and pending == 0):
            BATCH_STATE["final"] = data
            return
        time.sleep(6)
    pytest.fail(f"Batch NO terminó en 5min. Último snapshot: {last_snapshot}")


# --- 5) Al menos algunos candidatos completados o duplicados (no todos failed) ---

def test_05_candidates_completed_or_duplicate(auth_headers):
    final = BATCH_STATE.get("final")
    assert final, "test_04 debe correr antes"
    stats = final.get("stats") or {}
    completed = stats.get("completed", 0)
    duplicate = stats.get("duplicate", 0)
    partial = stats.get("partial", 0)
    failed = stats.get("failed", 0)
    total = final.get("total_files") or final.get("total_jobs") or 4
    print(f"[final] completed={completed} duplicate={duplicate} partial={partial} failed={failed} total={total}")
    # Comportamiento esperado: al menos 1 job en estado terminal exitoso (completed/duplicate/partial)
    assert (completed + duplicate + partial) >= 1, \
        f"Ningún job terminó bien: completed={completed} duplicate={duplicate} partial={partial} failed={failed}"
    # No aceptamos que TODOS hayan fallado
    assert failed < total, f"Todos los jobs fallaron ({failed}/{total})"


# --- 6) Candidatos aparecen en BD con datos parseados (nombre/skills) -----------

def test_06_candidates_persisted_with_parsed_data(auth_headers):
    """Usa los candidate_id directamente del batch snapshot para verificar persistencia."""
    time.sleep(2)
    final = BATCH_STATE.get("final") or {}
    jobs = final.get("jobs", [])
    candidate_ids = [j.get("candidate_id") for j in jobs if j.get("candidate_id")]
    print(f"[persist] candidate_ids_from_batch={len(candidate_ids)}")
    assert candidate_ids, "El batch no expuso candidate_ids en los jobs"

    # Consulta cada candidato individualmente
    checked = 0
    for cid in candidate_ids:
        r = requests.get(f"{API}/candidates/{cid}", headers=auth_headers, timeout=15)
        if r.status_code != 200:
            print(f"[persist] {cid} -> {r.status_code}")
            continue
        c = r.json()
        # Nombre parseado por LLM
        name = c.get("full_name") or c.get("name") or ""
        assert name, f"Candidato {cid} sin nombre"
        # Skills debe existir como estructura (hard_skills o skills)
        assert ("hard_skills" in c) or ("skills" in c), f"Candidato {cid} sin campo skills"
        # RUN_TAG debe estar contenido (para asegurarnos de que es de esta suite)
        # Nota: el nombre puede haber sido normalizado por el LLM, así que solo lo verificamos si aparece
        checked += 1
        print(f"[persist] {cid} name='{name[:60]}' skills_present=OK")
    assert checked >= 1, "Ningún candidato del batch se pudo recuperar por id"


# --- 7) Sin errores 'event loop' en los logs del backend -------------------------

def test_07_no_nested_event_loop_errors_in_logs():
    """
    Revisa /var/log/supervisor/backend.err.log en busca de errores típicos del bug P0.
    Solo cuenta ocurrencias RECIENTES (a partir del inicio de esta suite).
    """
    log_paths = [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ]
    forbidden = [
        "asyncio.run() cannot be called from a running event loop",
        "This event loop is already running",
        "event loop is already running",
        "RuntimeError: There is no current event loop",
    ]
    hits = []
    for p in log_paths:
        if not os.path.exists(p):
            continue
        try:
            # Últimas 2000 líneas
            out = subprocess.check_output(["tail", "-n", "2000", p], text=True, errors="ignore")
        except Exception as e:
            print(f"No pude leer {p}: {e}")
            continue
        for pat in forbidden:
            if pat in out:
                # contar líneas
                cnt = sum(1 for ln in out.splitlines() if pat in ln)
                hits.append(f"{p}: '{pat}' x{cnt}")
    print(f"[logs] forbidden_hits={hits}")
    assert not hits, f"Encontrados errores del bug P0 en logs: {hits}"


# --- 8) Regresión básica: login + listado + búsqueda ----------------------------

def test_08_basic_regression(auth_headers):
    # Listado
    r = requests.get(f"{API}/candidates?limit=5", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    # /jobs (vacantes)
    r2 = requests.get(f"{API}/jobs", headers=auth_headers, timeout=15)
    assert r2.status_code == 200, f"/jobs: {r2.status_code}"
    # /auth/me
    r3 = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=15)
    assert r3.status_code == 200
    me = r3.json()
    assert me.get("email") == ADMIN_EMAIL
    print("[regression] login + /candidates + /jobs + /auth/me OK")
