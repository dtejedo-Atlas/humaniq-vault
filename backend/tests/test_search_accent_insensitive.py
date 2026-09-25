"""Búsqueda insensible a acentos: «logistica» == «logística».

La normalización se aplica en dos pasadas: la literal conserva el comportamiento
histórico y sólo si no hay coincidencia se reintenta sin acentos.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from query_parser import parse_query, fold_accents  # noqa: E402
from hybrid_search_service import HybridSearchService  # noqa: E402

PAIRS = [
    ("logistica", "logística"),
    ("tecnologia", "tecnología"),
    ("gerente de logistica", "gerente de logística"),
    ("ingenieria", "ingeniería"),
    ("auditoria", "auditoría"),
]


def test_fold_accents():
    assert fold_accents("Logística") == "logistica"
    assert fold_accents("Ingeniería de Producción") == "ingenieria de produccion"
    assert fold_accents(None) == ""


def test_area_e_industria_iguales_con_y_sin_acentos():
    for plain, accented in PAIRS:
        a = parse_query(plain)
        b = parse_query(accented)
        assert a["area_funcional"] == b["area_funcional"], plain
        assert a["industria"] == b["industria"], plain


def test_no_cambia_lo_que_ya_funcionaba():
    # Consultas acentuadas y en inglés mantienen exactamente su interpretación previa
    assert parse_query("logística")["area_funcional"] == "supply_chain"
    assert parse_query("CFO")["seniority_index"] == 11
    assert parse_query("director de operaciones")["area_funcional"] == "operations"
    assert parse_query("ingeniería de producción")["seniority_index"] is None
    assert parse_query("java")["area_funcional"] is None


def test_keywords_cortos_no_se_cuelan_en_la_pasada_sin_acentos():
    # Al normalizar acentos, 'cio' NO debe convertir 'producción' en C-Level (nivel 11)
    assert parse_query("ingeniería de producción")["seniority_index"] is None
    assert parse_query("dirección de producción")["seniority_index"] == 9
    # Deuda preexistente, fuera de este alcance: en la pasada literal 'cio' sigue
    # colándose dentro de palabras sin acento ('produccion', 'operaciones').
    assert parse_query("produccion")["seniority_index"] == 11


def test_keyword_score_insensible_a_acentos():
    candidate = {"current_title": "Gerente de Logística", "current_company": "Almacén Central",
                 "ai_summary": "Experto en distribución", "skills": ["Logística inversa"]}
    score_plain, title_plain = HybridSearchService._calculate_keyword_score(
        None, candidate, parse_query("logistica"))
    score_accented, title_accented = HybridSearchService._calculate_keyword_score(
        None, candidate, parse_query("logística"))
    assert score_plain == score_accented > 0
    assert title_plain is title_accented is True
