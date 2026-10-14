"""Inventario SOLO LECTURA: fichas sintéticas de pruebas y repetidos en educación/certificaciones.

No escribe ni borra nada. Uso: python scripts/report_synthetic_and_education.py
"""
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')

REPORT = '/app/test_reports/synthetic_and_education_report.json'

NAME_PATTERNS = ['^zztest', '^test', 'prueba', 'synthetic', 'dummy', 'qa test', '^aaa', '^xxx']
EMAIL_PATTERNS = ['@test.com', '@example.com', '@test.mx', 'test@', 'qa@', '+test']


def norm(value):
    return ' '.join(str(value or '').casefold().split())


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]

    query = {'$or': [
        {'full_name': {'$regex': '|'.join(NAME_PATTERNS), '$options': 'i'}},
        {'email': {'$regex': '|'.join(p.replace('+', r'\+').replace('.', r'\.') for p in EMAIL_PATTERNS),
                   '$options': 'i'}},
        {'id': {'$regex': '^test-', '$options': 'i'}},
    ]}
    sinteticas = []
    async for c in db.candidates.find(query, {'_id': 0, 'id': 1, 'full_name': 1, 'email': 1,
                                              'created_at': 1, 'is_deleted': 1, 'source': 1}):
        sinteticas.append({'id': c['id'], 'nombre': c.get('full_name'), 'email': c.get('email'),
                           'creada': c.get('created_at'), 'borrada': bool(c.get('is_deleted')),
                           'origen': c.get('source')})
    sinteticas.sort(key=lambda r: str(r['creada']))
    print(f"Fichas sintéticas / de prueba encontradas en Atlas: {len(sinteticas)}")
    print(f"  activas: {sum(1 for r in sinteticas if not r['borrada'])} · "
          f"borradas (soft): {sum(1 for r in sinteticas if r['borrada'])}\n")
    for r in sinteticas:
        print(f"  {r['id']}  {str(r['nombre'])[:34]:<34} {str(r['email'])[:26]:<26} "
              f"{str(r['creada'])[:19]}  {'BORRADA' if r['borrada'] else 'activa'}")

    # Vacantes y usuarios de prueba (solo conteo)
    jobs = await db.jobs.count_documents({'title': {'$regex': 'test|prueba|zztest', '$options': 'i'}})
    users = await db.users.count_documents({'email': {'$regex': '@test\\.com|@example\\.com', '$options': 'i'}})
    print(f"\nVacantes con nombre de prueba: {jobs} · usuarios con correo de prueba: {users}")

    # Educación y certificaciones repetidas
    repetidos = {'education': [], 'certifications': []}
    con_datos = {'education': 0, 'certifications': 0}
    async for c in db.candidates.find({'is_deleted': {'$ne': True}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'education': 1, 'certifications': 1}):
        for field in ('education', 'certifications'):
            items = [i for i in (c.get(field) or []) if isinstance(i, (dict, str))]
            if items:
                con_datos[field] += 1
            keys = [norm(i.get('degree') if isinstance(i, dict) else i) + '|'
                    + norm(i.get('institution') if isinstance(i, dict) else '') for i in items]
            if len(keys) != len(set(keys)):
                repetidos[field].append({'id': c['id'], 'nombre': c.get('full_name'), 'items': items})
    print(f"\nFichas con educación capturada: {con_datos['education']} · con repetidos: {len(repetidos['education'])}")
    print(f"Fichas con certificaciones capturadas: {con_datos['certifications']} · "
          f"con repetidos: {len(repetidos['certifications'])}")

    with open(REPORT, 'w', encoding='utf-8') as handle:
        json.dump({'sinteticas': sinteticas, 'vacantes_prueba': jobs, 'usuarios_prueba': users,
                   'con_datos': con_datos,
                   'educacion_repetida': repetidos['education'],
                   'certificaciones_repetidas': repetidos['certifications']},
                  handle, ensure_ascii=False, default=str, indent=1)
    print(f"\nReporte: {REPORT}  (solo lectura, nada se escribió)")


if __name__ == '__main__':
    asyncio.run(main())
