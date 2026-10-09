"""E2E: CV nuevo con empleo anterior en telecom y actual en otra industria → company_industry inferido al cargar
y contado por el componente de industria (IA). Al final se elimina el candidato de prueba y su hash."""
import io
import os
import sys
import time
import requests
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

API = os.environ["API_URL"]
token = requests.post(f"{API}/api/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}, timeout=60).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
STAMP = str(int(time.time()))[-5:]
NAME = f"Prueba Telecom E2E {STAMP}"

LINES = [
    NAME, f"prueba.telecom.{STAMP}@example.com | +52 55 1234 5678 | Ciudad de México",
    "", "RESUMEN", "Director Comercial con 15 años de experiencia en ventas B2B, telecomunicaciones y bienes de consumo.",
    "", "EXPERIENCIA PROFESIONAL",
    "Director Comercial — Grupo Bimbo (alimentos y bienes de consumo) | Ene 2022 – Actual",
    "Dirección del canal moderno; equipo de 35 vendedores; crecimiento de 18% en ventas.",
    "",
    "Director de Ventas Empresariales — AT&T México (telecomunicaciones) | Mar 2016 – Dic 2021",
    "Venta de soluciones de conectividad móvil y fija a cuentas corporativas; equipo de 25 ejecutivos.",
    "",
    "Gerente de Ventas — Telcel (telecomunicaciones) | Ene 2011 – Feb 2016",
    "Gestión de distribuidores y ventas pospago en la región centro.",
    "", "EDUCACIÓN", "Licenciatura en Administración — ITAM, 2010", "MBA — IPADE, 2015",
    "", "IDIOMAS", "Español nativo, Inglés avanzado",
]


def make_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in LINES:
        c.drawString(60, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


pdf = make_pdf()
r = requests.post(f"{API}/api/candidates/upload-resume", headers=H, files={"file": (f"CV_{NAME}.pdf", pdf, "application/pdf")}, timeout=240)
assert r.status_code in (200, 201), (r.status_code, r.text[:400])
data = r.json()
cid = data.get("candidate_id") or (data.get("candidate") or {}).get("id")
assert cid, data
print(f"1. CV cargado → candidato {cid}")

cand = requests.get(f"{API}/api/candidates/{cid}", headers=H, timeout=60).json()
pcs = cand.get("previous_companies") or []
summary = [(p.get("company_name"), p.get("company_industry"), p.get("start_date"), p.get("end_date")) for p in pcs]
print("   previous_companies:", summary)
telecom_jobs = [p for p in pcs if p.get("company_industry") == "telecommunications"]
assert len(telecom_jobs) >= 1, "El empleo anterior en telecom no quedó como telecommunications"
assert all((p.get("company_industry") in (None,) or isinstance(p.get("company_industry"), str)) for p in pcs)
bimbo = next((p for p in pcs if "bimbo" in (p.get("company_name") or "").lower()), None)
assert bimbo is None or bimbo.get("company_industry") in ("consumer_goods", "food_beverage", None), bimbo
print(f"2. company_industry inferido al cargar: {len(telecom_jobs)} empleo(s) telecom; actual = {bimbo and bimbo.get('company_industry')} OK")

from db_connection import get_db  # noqa: E402
from scoring.engine_v3 import score_v3  # noqa: E402
db = get_db()
job = db.jobs.find_one({"id": "a5a9ceb5-6a43-4547-bd30-7966a96959b5"}, {"_id": 0})
cdoc = db.candidates.find_one({"id": cid}, {"_id": 0, "embedding": 0})
res = score_v3(cdoc, job)
ia = res["component_breakdown"]["IA"]
ev = ia["evidence"]
print(f"3. IA raw={ia['raw']} ci={ia['confidence']} target_years={ev.get('target_years')} evidencia={[(e['company'], e['industry'], e['years']) for e in ev.get('evidence', [])]}")
assert ev.get("target_years", 0) >= 4, "El componente de industria no contó los años en telecom"
assert ia["raw"] > 0.4, ia
ko = next(k for k in res["knockout_results"]["results"] if k["criterion"] == "industry")
assert ko["status"] == "cumple", ko
print(f"4. Knockout de industria: {ko['status']} ({ko.get('note')}) OK")

# limpieza
dr = requests.delete(f"{API}/api/candidates/{cid}", headers=H, timeout=60)
db.candidates.delete_one({"id": cid})
db.cv_hashes.delete_many({"candidate_id": cid})
db.cv_versions.delete_many({"candidate_id": cid})
db.cv_fulltext.delete_many({"candidate_id": cid})
print(f"5. limpieza: delete API {dr.status_code}; candidato de prueba eliminado de la base OK")
print("\nTODO OK")
