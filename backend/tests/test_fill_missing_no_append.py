"""Causa raíz de los empleos repetidos: `fill_missing_from_extras` ya no concatena historial.

Mongo en memoria (fake), no toca Atlas. Uso: python tests/test_fill_missing_no_append.py
"""
import asyncio
import sys

sys.path.insert(0, '/app/backend')
from cv_hash_service import CVHashService  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


class FakeCandidates:
    def __init__(self, docs):
        self.docs = {d['id']: d for d in docs}
        self.updates = {}

    async def find_one(self, query, projection=None):
        return self.docs.get(query.get('id'))

    async def update_one(self, query, update):
        self.updates[query['id']] = update['$set']
        self.docs[query['id']].update(update['$set'])


class FakeDB:
    def __init__(self, docs):
        self.candidates = FakeCandidates(docs)


KEEP_HISTORY = [
    {'company_name': 'SGS Mexico', 'title': 'Sr. Technical Sales', 'start_date': '2022-05', 'end_date': None},
    {'company_name': 'PEMEX GAS Y PETROQUÍMICA BÁSICA', 'title': 'Professional Intern',
     'start_date': '2013', 'end_date': '2013'},
]
EXTRA_HISTORY = [
    # mismo CV, parseado distinto: solo cambia el formato del nombre y del título
    {'company_name': 'SGS Mexico', 'title': 'Sr. Technical Sales', 'start_date': '2022-05', 'end_date': None,
     'description': 'otra redacción'},
    {'company_name': 'PEMEX Gas y Petroquímica Básica', 'title': 'Professional Internship',
     'start_date': '2013', 'end_date': '2013'},
]

db = FakeDB([
    {'id': 'keep', 'previous_companies': list(KEEP_HISTORY), 'skills': ['Ventas'], 'email': None,
     'education': [{'degree': 'Lic. Administración', 'institution': 'ITESM'}], 'languages': ['Inglés']},
    {'id': 'extra', 'previous_companies': list(EXTRA_HISTORY), 'skills': ['Negociación', 'ventas', 'VENTAS'],
     'email': 'a@b.com', 'phone': '55',
     'education': [{'degree': 'Licenciatura en Administración', 'institution': 'ITESM'}],
     'languages': ['ingles', 'Francés']},
])
service = CVHashService(db)
updates = asyncio.run(service.fill_missing_from_extras('keep', ['extra']))

check('el historial laboral NO se concatena', 'previous_companies' not in updates, str(list(updates.keys())))
check('la ficha conservada mantiene sus 2 empleos', len(db.candidates.docs['keep']['previous_companies']) == 2,
      str(len(db.candidates.docs['keep']['previous_companies'])))
check('la educación NO se concatena', 'education' not in updates, str(updates.get('education')))
check('sí completa campos escalares vacíos', updates.get('email') == 'a@b.com')
check('sí completa el teléfono faltante', updates.get('phone') == '55')
check('las listas simples se unen sin repetir (ignorando mayúsculas)',
      updates.get('skills') == ['Ventas', 'Negociación'], str(updates.get('skills')))
check('las listas simples se unen ignorando acentos',
      updates.get('languages') == ['Inglés', 'Francés'], str(updates.get('languages')))

# Si la ficha conservada no tiene historial ni educación, sí se copian los del duplicado
db2 = FakeDB([
    {'id': 'keep', 'previous_companies': [], 'skills': [], 'education': [], 'certifications': []},
    {'id': 'extra', 'previous_companies': list(EXTRA_HISTORY),
     'education': [{'degree': 'Licenciatura', 'institution': 'ITESM'}],
     'certifications': [{'name': 'PMP'}]},
])
updates2 = asyncio.run(CVHashService(db2).fill_missing_from_extras('keep', ['extra']))
check('si la ficha conservada no tiene empleos, se copian los del duplicado',
      len(updates2.get('previous_companies') or []) == 2, str(len(updates2.get('previous_companies') or [])))
check('si no tiene educación ni certificaciones, se copian',
      len(updates2.get('education') or []) == 1 and len(updates2.get('certifications') or []) == 1)

print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
