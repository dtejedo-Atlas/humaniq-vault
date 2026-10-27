"""Reporte de cierre del piloto, por consultora. SOLO LECTURA: no escribe nada.

Uso:
    python3 -m scripts.pilot_report                       # desde el inicio del piloto hasta hoy
    python3 -m scripts.pilot_report --from 2026-10-21 --to 2026-10-30
"""
import argparse
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from scripts.db_connection import get_db  # noqa: E402

PILOT_START = "2026-10-21"


def fmt(dt: str) -> str:
    if not dt:
        return "nunca"
    return str(dt)[:16].replace("T", " ")


def main(date_from: str, date_to: str):
    db = get_db()
    lo, hi = f"{date_from}T00:00:00", f"{date_to}T23:59:59"
    rng = {"$gte": lo, "$lte": hi}

    users = list(db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1,
                                    "role": 1, "is_active": 1, "last_login": 1}))
    by_id = {u["id"]: u for u in users}

    def count_logs(action, uid):
        return db.activity_logs.count_documents({"action": action, "user_id": uid, "timestamp": rng})

    print(f"\nREPORTE DEL PILOTO — {date_from} a {date_to}  (solo lectura)\n")
    header = (f"{'Consultora':34s} {'Rol':12s} {'Último acceso':17s} "
              f"{'Vac.':>5s} {'CVs':>5s} {'IA':>4s} {'PDFs':>5s} {'Notas':>6s} {'Asig.':>6s}")
    print(header)
    print("-" * len(header))

    totals = dict(jobs=0, cvs=0, refines=0, pdfs=0, notes=0, assigns=0)
    for u in sorted(users, key=lambda x: (not x.get("is_active"), x.get("email", ""))):
        uid = u["id"]
        jobs = db.jobs.count_documents({"created_by": uid, "created_at": rng,
                                        "is_deleted": {"$ne": True}})
        cvs = count_logs("candidate_uploaded", uid) or db.candidates.count_documents(
            {"created_by": uid, "created_at": rng, "is_deleted": {"$ne": True}})
        refines = count_logs("ai_refine", uid)
        pdfs = db.exports.count_documents({"user_id": uid, "created_at": rng})
        notes = count_logs("note_added", uid)
        assigns = count_logs("candidate_assigned", uid)

        if not any([jobs, cvs, refines, pdfs, notes, assigns]) and not u.get("last_login"):
            continue

        name = (u.get("name") or u.get("email", ""))[:33]
        estado = u.get("role", "") + ("" if u.get("is_active") else " (baja)")
        print(f"{name:34s} {estado[:12]:12s} {fmt(u.get('last_login')):17s} "
              f"{jobs:5d} {cvs:5d} {refines:4d} {pdfs:5d} {notes:6d} {assigns:6d}")
        for k, v in zip(totals, (jobs, cvs, refines, pdfs, notes, assigns)):
            totals[k] += v

    print("-" * len(header))
    print(f"{'TOTAL':34s} {'':12s} {'':17s} {totals['jobs']:5d} {totals['cvs']:5d} "
          f"{totals['refines']:4d} {totals['pdfs']:5d} {totals['notes']:6d} {totals['assigns']:6d}")

    print("\nColumnas: Vac.=vacantes creadas · CVs=CVs subidos · IA=veces que usó "
          "\"Afinar con IA\" · PDFs=shortlists exportados · Notas · Asig.=candidatos asignados")
    print("Nota: 'Último acceso' es la última sesión registrada; la plataforma no guarda "
          "el historial completo de inicios de sesión.\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", default=PILOT_START)
    p.add_argument("--to", dest="date_to",
                   default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    a = p.parse_args()
    main(a.date_from, a.date_to)
