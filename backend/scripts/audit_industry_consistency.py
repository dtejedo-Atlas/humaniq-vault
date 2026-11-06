"""Auditoría de la industria asignada a cada candidato. SOLO LECTURA.

Compara `candidates.industry` contra las industrias de su trayectoria
(`previous_companies[].company_industry`) para detectar perfiles de giro mixto
o con industria inconsistente.

Uso:
    python3 -m scripts.audit_industry_consistency
    python3 -m scripts.audit_industry_consistency --show 15
"""
import argparse
import os
import sys
from collections import Counter

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from scripts.db_connection import get_db  # noqa: E402


def main(show: int):
    db = get_db()
    cands = list(db.candidates.find(
        {"is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "full_name": 1, "industry": 1, "current_company": 1,
         "previous_companies": 1},
    ))

    buckets = {"ok": [], "mixto_coincide": [], "mixto_no_coincide": [],
               "no_coincide": [], "sin_trayectoria": [], "sin_industria": []}

    for c in cands:
        ind = (c.get("industry") or "").strip().lower()
        traj = [(p.get("company_industry") or "").strip().lower()
                for p in (c.get("previous_companies") or [])]
        traj = [t for t in traj if t]
        distinct = set(traj)
        if not ind:
            buckets["sin_industria"].append((c, traj))
        elif not traj:
            buckets["sin_trayectoria"].append((c, traj))
        elif len(distinct) == 1:
            buckets["ok" if ind in distinct else "no_coincide"].append((c, traj))
        else:
            buckets["mixto_coincide" if ind in distinct else "mixto_no_coincide"].append((c, traj))

    total = len(cands)
    print(f"\nAUDITORÍA DE INDUSTRIA — {total} candidatos activos (solo lectura)\n")
    etiquetas = {
        "ok": "Trayectoria de un solo giro y la industria coincide",
        "mixto_coincide": "Giro MIXTO, pero la industria elegida sí está en su trayectoria",
        "mixto_no_coincide": "Giro MIXTO y la industria elegida NO está en su trayectoria",
        "no_coincide": "Un solo giro y la industria elegida NO coincide",
        "sin_trayectoria": "Sin industrias en la trayectoria (no se puede auditar)",
        "sin_industria": "Sin industria asignada",
    }
    for k, label in etiquetas.items():
        n = len(buckets[k])
        print(f"{n:5d}  ({n / total * 100:5.1f}%)  {label}")

    for k in ("mixto_no_coincide", "no_coincide"):
        rows = buckets[k]
        if not rows:
            continue
        print(f"\n--- {etiquetas[k]} ({len(rows)}) — primeros {show} ---")
        for c, traj in rows[:show]:
            cnt = ", ".join(f"{i} x{n}" for i, n in Counter(traj).most_common())
            print(f"  {(c.get('full_name') or c['id'])[:34]:36s} asignada={c.get('industry'):22s} trayectoria=[{cnt}]")

    print(f"\n--- Giro mixto con industria coincidente ({len(buckets['mixto_coincide'])}) "
          f"— primeros {show} ---")
    for c, traj in buckets["mixto_coincide"][:show]:
        cnt = ", ".join(f"{i} x{n}" for i, n in Counter(traj).most_common())
        print(f"  {(c.get('full_name') or c['id'])[:34]:36s} asignada={c.get('industry'):22s} trayectoria=[{cnt}]")
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--show", type=int, default=10)
    main(p.parse_args().show)
