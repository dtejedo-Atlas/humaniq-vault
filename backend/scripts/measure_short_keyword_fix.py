"""Mide el impacto de exigir límite de palabra a keywords cortos (CFO, CIO, VP).

Sólo simula: parchea el comparador en memoria y compara resultados. No modifica
código de producción ni datos.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

import query_parser  # noqa: E402
from server import hybrid_search_service  # noqa: E402

QUERIES = [
    "director de operaciones", "gerente de operaciones", "director de producción",
    "jefe de produccion", "operaciones logísticas", "contabilidad", "logística",
    "CFO", "CIO", "VP de ventas", "recursos humanos", "marketing digital",
    "ingeniería de producción", "compras", "ventas",
]

original_contains = query_parser._contains


def strict_contains(keyword, text, strict_short=False):
    return original_contains(keyword, text, strict_short=True)


async def snapshot():
    out = {}
    for query in QUERIES:
        results = await hybrid_search_service.search(query=query, filters={}, use_semantic=True, limit=30)
        parsed = query_parser.parse_query(query)
        out[query] = {
            "seniority_index": parsed["seniority_index"],
            "area": parsed["area_funcional"],
            "resultados": [(item["id"], item["match_score"]) for item in results],
        }
    return out


async def main():
    before = await snapshot()
    query_parser._contains = strict_contains
    after = await snapshot()
    query_parser._contains = original_contains

    report = {}
    for query in QUERIES:
        a, b = before[query], after[query]
        ids_a = [item[0] for item in a["resultados"]]
        ids_b = [item[0] for item in b["resultados"]]
        scores_a = dict(a["resultados"])
        scores_b = dict(b["resultados"])
        report[query] = {
            "seniority": f"{a['seniority_index']} → {b['seniority_index']}",
            "area": f"{a['area']} → {b['area']}",
            "resultados": f"{len(ids_a)} → {len(ids_b)}",
            "identico": a["resultados"] == b["resultados"],
            "entraron": len([i for i in ids_b if i not in ids_a]),
            "salieron": len([i for i in ids_a if i not in ids_b]),
            "score_subio": len([i for i in scores_a if i in scores_b and scores_b[i] > scores_a[i]]),
            "score_bajo": len([i for i in scores_a if i in scores_b and scores_b[i] < scores_a[i]]),
        }
    Path("/app/test_reports/short_keyword_boundary_impact.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for query, data in report.items():
        flag = "IGUAL " if data["identico"] else "CAMBIO"
        print(f"{flag} {query!r:30} seniority {data['seniority']:12} area {data['area']:28} "
              f"resultados {data['resultados']:10} +{data['entraron']}/-{data['salieron']} "
              f"score+{data['score_subio']} score-{data['score_bajo']}")


if __name__ == "__main__":
    asyncio.run(main())
