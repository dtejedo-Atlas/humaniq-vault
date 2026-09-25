"""Catálogo Humaniq: normalización de presentación → claves del motor.

No toca scoring: sólo verifica que lo guardado sea una clave que el motor conoce.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from affinity_matrices import FUNCTIONAL_AFFINITY  # noqa: E402
from humaniq_catalog import (AREAS, SENIORITY_LEVELS, AREA_TO_ENGINE, SENIORITY_TO_ENGINE,  # noqa: E402
                             ENGINE_AREAS, normalize_classification, resolve_area,
                             resolve_seniority, public_catalog)
from models import SeniorityLevel  # noqa: E402


def test_catalog_shape():
    assert len(AREAS) == 15
    assert sum(len(area["subareas"]) for area in AREAS) == 105
    assert len(SENIORITY_LEVELS) == 13


def test_engine_keys_exist_in_affinity_matrix():
    assert set(ENGINE_AREAS) == set(FUNCTIONAL_AFFINITY)
    for engine in AREA_TO_ENGINE.values():
        assert engine is None or engine in FUNCTIONAL_AFFINITY


def test_engine_seniorities_are_valid_enum_values():
    valid = {level.value for level in SeniorityLevel}
    assert set(SENIORITY_TO_ENGINE.values()) <= valid


def test_salud_y_esg_sin_equivalencia_artificial():
    assert AREA_TO_ENGINE["salud"] is None
    assert AREA_TO_ENGINE["sustentabilidad"] is None
    result = normalize_classification({"functional_area": "salud", "seniority": "direccion"})
    assert result["functional_area"] is None
    assert result["presentation_area"] == "salud"
    assert result["no_engine_equivalent"] == ["salud"]


def test_normaliza_ingles_mayusculas_y_claves_historicas():
    for raw, engine in [("finance", "finance"), ("FINANCE", "finance"), ("Finanzas", "finance"),
                        ("it", "technology"), ("IT", "technology"), ("it_technology", "technology"),
                        ("manufacturing", "operations"), ("engineering", "operations"),
                        ("customer service", "operations"), ("construction", "operations"),
                        ("supply chain", "supply_chain"), ("accounting", "finance"),
                        ("general_management", "general_management")]:
        assert resolve_area(raw)["engine_area"] == engine, raw


def test_subarea_no_es_tapada_por_alias_de_area():
    assert resolve_area("finanzas", "contraloria")["presentation_subarea"] == "contraloria"
    assert resolve_area("finanzas", "Contraloría")["presentation_subarea"] == "contraloria"
    # Subárea de otra área no se acepta
    assert resolve_area("finanzas", "ciberseguridad")["presentation_subarea"] is None


def test_seniority_ingles_y_espanol():
    for raw, engine in [("manager", "manager"), ("Gerencia", "manager"), ("gerencia_sr", "manager"),
                        ("senior manager", "manager"), ("ceo", "c_level"), ("intern", "entry"),
                        ("Subdirección", "director"), ("director", "director")]:
        assert resolve_seniority(raw)["engine_seniority"] == engine, raw


def test_valor_irreconocible_no_se_guarda():
    result = normalize_classification({"functional_area": "astrología", "seniority": "supremo"})
    assert result["functional_area"] is None
    assert result["seniority"] is None
    assert len(result["out_of_catalog"]) == 2


def test_public_catalog_expone_mapeo():
    catalog = public_catalog()
    assert len(catalog["areas"]) == 15
    assert len(catalog["seniority_levels"]) == 13
    assert [level["rank"] for level in catalog["seniority_levels"]] == list(range(1, 14))
    assert all("engine_area" in area for area in catalog["areas"])
