"""Snapshot de resultados de búsqueda para comprobar que normalizar acentos no altera el ranking.

Uso: python3 search_snapshot.py <archivo_salida>
"""
import json
import os
import sys
import requests
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / "frontend" / ".env")
load_dotenv(Path(__file__).parent.parent / ".env")

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
QUERIES = [
    "contabilidad", "logística", "logistica", "gerente de logística", "gerente de logistica",
    "CFO", "ventas", "director de operaciones", "java", "recursos humanos",
    "tecnología", "tecnologia", "ingeniería de producción", "compras", "marketing digital",
]


def call(path, token, method="GET", **params):
    response = requests.request(method, f"{API}{path}", params=params,
                                headers={"Authorization": f"Bearer {token}"}, timeout=120)
    response.raise_for_status()
    return response.json()


def login():
    return os.environ["SNAPSHOT_TOKEN"]


def main(out_path):
    token = login()
    snapshot = {}
    for query in QUERIES:
        data = call("/api/search/hybrid", token, method="POST", query=query, limit=30)
        snapshot[query] = [
            {"id": item["id"], "score": item.get("match_score"), "name": item.get("full_name")}
            for item in data["results"]
        ]
        print(f"{query!r}: {len(snapshot[query])} resultados")
    Path(out_path).write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
