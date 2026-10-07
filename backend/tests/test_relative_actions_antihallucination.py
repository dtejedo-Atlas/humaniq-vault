"""Acciones relativas, no-negociables custom vía IA (ajuste de K) y anti-alucinación de citas (sin red)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_refine_service import AIRefineService, quote_in_text, _norm_text

CV = "Dirigí la función financiera completa (tesorería, contabilidad y FP&A) en Grupo Éxito 2015–2021.\nInglés avanzado."


def test_quote_verification_normalizes_accents_and_spaces():
    assert quote_in_text("dirigi la funcion   financiera completa", CV)
    assert quote_in_text("Inglés avanzado.", CV)
    assert not quote_in_text("Lideré equipos de 40 vendedores", CV)
    assert not quote_in_text("corto", CV)  # demasiado corta para contar como evidencia
    assert _norm_text("Éxito, S.A.") == "exito s a"


def _rows(n, hms):
    return [{"candidate_id": f"c{i}", "match_score_v3": hms[i], "knockout_results": {"K": 1.0, "results": []}} for i in range(n)]


def test_relative_actions_top5_backup10_and_quality():
    rows = AIRefineService.unify(_rows(20, [80, 70, 66, 60, 58, 57, 56, 56, 55, 55, 55, 55, 55, 55, 55, 55, 54, 50, 40, 30]), [])
    actions = [r["action"] for r in rows]
    assert actions[:5] == ["interview"] * 5 and actions[5:15] == ["backup"] * 10
    assert actions[15:] == ["low_priority"] * 5  # tope de 10 backups; HMS < 55 nunca es Entrevistar/Backup
    assert [r["quality"] for r in rows[:4]] == ["excelente", "bueno", "bueno", "aceptable"] and rows[-1]["quality"] == "debil"
    assert "save_for_other_role" not in actions


def test_custom_knockout_adjusts_k_and_order():
    base = _rows(4, [70, 65, 60, 58])
    base[3]["knockout_results"] = {"K": 0.0, "results": []}  # fatal del motor
    ko = {"id": "k", "kind": "knockout", "severity": "important", "key": "lidera finanzas", "text": "Lidera finanzas", "status": "done",
          "results": {"c0": {"status": "no_cumple", "no_evidence": True}, "c1": {"status": "parcial", "quote": "x"}, "c2": {"status": "cumple", "quote": "y"}}}
    rows = AIRefineService.unify(base, [ko], {"lidera finanzas"})
    by = {r["candidate_id"]: r for r in rows}
    assert by["c0"]["match_score_v3"] == 35 and by["c0"]["k_custom"] == 0.5 and by["c0"]["action"] == "low_priority"
    assert by["c1"]["match_score_v3"] == 55 and by["c1"]["action"] == "interview"
    assert by["c2"]["match_score_v3"] == 60 and rows[0]["candidate_id"] == "c2"  # quien cumple va primero
    assert by["c3"]["action"] == "do_not_advance_knockout"
    assert rows[-1]["candidate_id"] == "c3" and rows[-2]["candidate_id"] == "c0"  # fatal al final, luego el que falla


def test_fatal_custom_knockout_and_unevaluated_neutral():
    base = _rows(3, [70, 65, 60])
    ko = {"id": "k", "kind": "knockout", "severity": "fatal", "key": "cpa", "text": "CPA", "status": "done",
          "results": {"c0": {"status": "no_cumple"}}}
    rows = AIRefineService.unify(base, [ko], {"cpa"})
    by = {r["candidate_id"]: r for r in rows}
    assert by["c0"]["match_score_v3"] == 0 and by["c0"]["action"] == "do_not_advance_knockout"
    assert by["c1"]["k_custom"] == 1.0 and by["c1"]["custom_knockouts"][0]["status"] == "no_evaluado" and by["c1"]["action"] == "interview"


def test_inactive_knockout_criteria_ignored():
    base = _rows(2, [70, 65])
    ko = {"id": "k", "kind": "knockout", "severity": "important", "key": "viejo", "text": "Viejo", "status": "done",
          "results": {"c0": {"status": "no_cumple"}}}
    rows = AIRefineService.unify(base, [ko], set())  # ya no está en el scorecard
    assert rows[0]["candidate_id"] == "c0" and rows[0]["match_score_v3"] == 70 and rows[0]["custom_knockouts"] == []
