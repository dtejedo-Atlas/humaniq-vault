"""
Tests para el fix de "Candidate has no attribute 'education'" y validación
defensiva en POST /api/candidates/upload-resume.

Cobertura:
  1) Funciones safe_int/safe_string/safe_list/clean_previous_company/
     clean_previous_companies definidas en server.py.
  2) El modelo Candidate NO debe exponer atributo `education`
     (linea 1269 server.py - referencia eliminada).
  3) Endpoint POST /api/candidates/upload-resume procesa PDF sin
     lanzar "'Candidate' object has no attribute 'education'".
  4) DocumentParser.extract_text_from_bytes funciona para PDFs.
"""
import io
import os
import sys
import pytest
import requests

# Garantizar import de modulos del backend
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://atlas-recruiting-ai.preview.emergentagent.com",
).rstrip("/")

# Test credentials from environment with defaults for local testing
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "test_utf8@atlas.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "Humaniq123")


# ============= FIXTURES =============

@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_token(api_client):
    r = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed ({r.status_code}): {r.text[:200]}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def authed_session(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    return s


@pytest.fixture(scope="session")
def sample_pdf_bytes():
    """Genera un PDF mínimo con texto de CV usando reportlab."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    lines = [
        "TEST_RESILIENCE Candidato Uno",
        "Email: test_resilience_one@example.com",
        "Telefono: +52 55 1234 5678",
        "Ciudad: Ciudad de Mexico, Mexico",
        "LinkedIn: https://linkedin.com/in/test-resilience",
        "",
        "Experiencia: 10 anos como Gerente de Proyectos",
        "Empresa actual: Acme Corp - Project Manager (2020 - Presente)",
        "Empresa anterior: Globex - Senior Analyst (2015 - 2020)",
        "",
        "Skills: Python, Liderazgo, SAP, BI",
        "Idiomas: Espanol, Ingles",
        "",
        "Educacion: Licenciatura en Ingenieria Industrial - UNAM",
    ]
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.showPage()
    c.save()
    return buf.getvalue()


# ============= UNIT TESTS: helpers de validacion =============

class TestSafeHelpers:
    def test_safe_int_handles_none(self):
        from server import safe_int
        assert safe_int(None) is None
        assert safe_int(None, default=0) == 0

    def test_safe_int_passthrough_int(self):
        from server import safe_int
        assert safe_int(7) == 7

    def test_safe_int_float_to_int(self):
        from server import safe_int
        assert safe_int(3.9) == 3

    def test_safe_int_from_messy_string(self):
        from server import safe_int
        assert safe_int("10 anos") == 10
        assert safe_int("10+") == 10
        assert safe_int("  5  ") == 5

    def test_safe_int_unparseable_returns_default(self):
        from server import safe_int
        assert safe_int("N/A") is None
        assert safe_int("N/A", default=0) == 0
        assert safe_int([1, 2, 3]) is None

    def test_safe_string_handles_none_and_empty(self):
        from server import safe_string
        assert safe_string(None) is None
        assert safe_string("") is None
        assert safe_string("   ") is None
        assert safe_string("ok") == "ok"
        assert safe_string("  hola ") == "hola"

    def test_safe_string_non_string_cast(self):
        from server import safe_string
        assert safe_string(123) == "123"

    def test_safe_list_handles_invalid(self):
        from server import safe_list
        assert safe_list(None) == []
        assert safe_list("nope") == []
        assert safe_list([1, 2]) == [1, 2]
        assert safe_list((1, 2)) == [1, 2]

    def test_clean_previous_company_irrecoverable_returns_none(self):
        from server import clean_previous_company
        assert clean_previous_company({}) is None
        assert clean_previous_company({"company_name": None, "title": None}) is None
        assert clean_previous_company("not a dict") is None

    def test_clean_previous_company_alternate_keys(self):
        from server import clean_previous_company
        out = clean_previous_company({"company": "Acme", "position": "PM"})
        assert out is not None
        assert out["company_name"] == "Acme"
        assert out["title"] == "PM"

    def test_clean_previous_company_fills_defaults(self):
        from server import clean_previous_company
        out = clean_previous_company({"company_name": "Acme"})
        assert out["company_name"] == "Acme"
        assert out["title"] == "Puesto no especificado"

    def test_clean_previous_companies_skips_invalid(self):
        from server import clean_previous_companies
        data = [
            {"company_name": "Acme", "title": "PM"},
            {},                                # se descarta
            "not a dict",                      # se descarta
            {"position": "Analyst"},           # se conserva (titulo)
        ]
        out = clean_previous_companies(data)
        assert isinstance(out, list)
        assert len(out) == 2
        assert out[0]["company_name"] == "Acme"
        assert out[1]["title"] == "Analyst"

    def test_clean_previous_companies_handles_non_list(self):
        from server import clean_previous_companies
        assert clean_previous_companies(None) == []
        assert clean_previous_companies("garbage") == []


# ============= UNIT TESTS: modelo Candidate / education removido =============

class TestCandidateModelNoEducation:
    def test_candidate_model_has_no_education_field(self):
        from models import Candidate
        # education NO debe existir como campo del modelo
        assert "education" not in Candidate.model_fields, (
            "El modelo Candidate no debe declarar campo 'education'"
        )

    def test_candidate_instance_has_no_education_attr(self):
        from models import Candidate
        c = Candidate(id="test-id", full_name="TEST Candidate", created_by="x")
        # No debe existir el atributo (causaba AttributeError previo)
        assert not hasattr(c, "education")

    def test_create_candidate_with_messy_data_does_not_raise(self):
        """Simula el flujo defensivo del endpoint upload-resume."""
        from server import (
            safe_int, safe_string, safe_list, clean_previous_companies,
        )
        from models import Candidate, PreviousCompany

        parsed_data = {
            "full_name": "  TEST_Defensive  ",
            "email": "  ",                  # empty -> None
            "phone": None,
            "years_experience": "10 anos",  # string -> 10
            "skills": None,                 # None -> []
            "languages": "no list",         # invalid -> []
            "previous_companies": [
                {"company": "Acme", "position": "PM"},  # alt keys
                {},                                     # skipped
                {"company_name": "Globex"},             # only company
            ],
        }
        cleaned = clean_previous_companies(parsed_data["previous_companies"])
        pcs = [PreviousCompany(**pc) for pc in cleaned]

        c = Candidate(
            id="test-defensive",
            full_name=safe_string(parsed_data["full_name"], "Sin nombre"),
            email=safe_string(parsed_data.get("email")),
            phone=safe_string(parsed_data.get("phone")),
            years_experience=safe_int(parsed_data.get("years_experience")),
            skills=safe_list(parsed_data.get("skills")),
            languages=safe_list(parsed_data.get("languages")),
            previous_companies=pcs,
            created_by="tester",
        )
        assert c.full_name == "TEST_Defensive"
        assert c.email is None
        assert c.phone is None
        assert c.years_experience == 10
        assert c.skills == []
        assert c.languages == []
        assert len(c.previous_companies) == 2


# ============= UNIT TESTS: DocumentParser =============

class TestDocumentParser:
    def test_extract_text_from_pdf_bytes(self, sample_pdf_bytes):
        from document_parser import DocumentParser
        text = DocumentParser.extract_text_from_bytes(
            sample_pdf_bytes, "application/pdf"
        )
        assert isinstance(text, str)
        assert len(text.strip()) > 50
        assert "TEST_RESILIENCE" in text or "Candidato" in text


# ============= INTEGRATION: POST /api/candidates/upload-resume =============

class TestUploadResumeNoEducationError:
    def test_login_works(self, auth_token):
        assert isinstance(auth_token, str) and len(auth_token) > 20

    def test_upload_pdf_does_not_crash_with_education_error(
        self, authed_session, sample_pdf_bytes
    ):
        files = {
            "file": (
                "TEST_resilience_cv.pdf",
                sample_pdf_bytes,
                "application/pdf",
            )
        }
        # No mandar Content-Type JSON en multipart
        s = requests.Session()
        s.headers.update(authed_session.headers.copy())
        s.headers.pop("Content-Type", None)

        r = s.post(
            f"{BASE_URL}/api/candidates/upload-resume",
            files=files,
            timeout=120,
        )
        # El endpoint NO debe devolver 500
        assert r.status_code in (200, 201), (
            f"upload-resume devolvio {r.status_code}: {r.text[:500]}"
        )

        body = r.json()
        body_str = str(body).lower()

        # Validar que NO aparece el error de 'education'
        assert "has no attribute 'education'" not in body_str, (
            f"Regresion: error 'education' presente en respuesta: {body_str[:500]}"
        )
        assert "candidate' object has no attribute" not in body_str, (
            f"Otro AttributeError en Candidate: {body_str[:500]}"
        )

        # Estado aceptable: success, partial_success o duplicate_*
        status_val = body.get("status")
        assert status_val in (
            "success", "partial_success", "duplicate_blocked",
            "duplicate_suggested",
        ), f"Estado inesperado: {status_val} - body={body_str[:500]}"

    def test_upload_unsupported_format_returns_failed_not_500(self, authed_session):
        s = requests.Session()
        s.headers.update(authed_session.headers.copy())
        s.headers.pop("Content-Type", None)
        files = {"file": ("bad.txt", b"hola mundo", "text/plain")}
        r = s.post(
            f"{BASE_URL}/api/candidates/upload-resume",
            files=files,
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "failed"
        # Error de formato debe estar reportado, no AttributeError
        body_str = str(body).lower()
        assert "education" not in body_str
