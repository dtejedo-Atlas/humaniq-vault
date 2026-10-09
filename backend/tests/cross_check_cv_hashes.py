"""Cruce de una carpeta de CVs (CSV con sha256 de archivo) contra cv_hashes en Atlas.

CSV esperado: encabezados que incluyan el nombre de archivo y el sha256
(se aceptan variantes: archivo/file/file_name/nombre y sha256/sha256_file/hash).

Uso: python tests/cross_check_cv_hashes.py /ruta/archivo.csv [--csv-out /tmp/cruce.csv]
"""
import asyncio
import csv
import os
import re
import sys
import unicodedata

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

CSV_PATH = sys.argv[1]
OUT_PATH = sys.argv[sys.argv.index('--csv-out') + 1] if '--csv-out' in sys.argv else '/tmp/cruce_cvs.csv'
NAME_KEYS = ('archivo', 'file', 'file_name', 'filename', 'nombre', 'nombre_archivo', 'cv')
HASH_KEYS = ('sha256', 'sha256_file', 'hash', 'sha', 'sha_256', 'checksum')


def norm(text):
    text = unicodedata.normalize('NFKD', (text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def name_from_file(file_name):
    stem = os.path.splitext(os.path.basename(file_name or ''))[0]
    stem = re.sub(r'\b(cv|curriculum|vitae|resume|hoja de vida|act|actualizado|final|v\d+|\d{4})\b', ' ', norm(stem))
    return ' '.join(stem.split())


def read_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        headers = {norm(h).replace(' ', '_'): h for h in (reader.fieldnames or [])}
        name_col = next((headers[k] for k in NAME_KEYS if k in headers), None)
        hash_col = next((headers[k] for k in HASH_KEYS if k in headers), None)
        rows = list(reader)
    if not name_col or not hash_col:
        print('Encabezados detectados:', list(headers))
        raise SystemExit('No pude identificar las columnas de archivo y sha256 en el CSV.')
    return [(r[name_col].strip(), (r[hash_col] or '').strip().lower()) for r in rows if (r.get(name_col) or '').strip()]


async def main():
    rows = read_rows(CSV_PATH)
    print(f'CVs en el CSV: {len(rows)}')
    client = AsyncIOMotorClient(os.environ['ATLAS_URI'])
    db = client[os.environ['ATLAS_DB_NAME']]

    hashes = [h for _, h in rows if h]
    hash_map = {}
    async for doc in db.cv_hashes.find({'sha256_file': {'$in': hashes}, 'active': True}, {'_id': 0}):
        hash_map.setdefault(doc['sha256_file'], []).append(doc)

    candidate_ids = {d['candidate_id'] for docs in hash_map.values() for d in docs}
    candidates = {}
    async for c in db.candidates.find({'id': {'$in': list(candidate_ids)}, 'is_deleted': {'$ne': True}},
                                      {'_id': 0, 'id': 1, 'full_name': 1, 'email': 1}):
        candidates[c['id']] = c

    # Índice por nombre normalizado de todos los candidatos vigentes
    by_name = {}
    async for c in db.candidates.find({'is_deleted': {'$ne': True}}, {'_id': 0, 'id': 1, 'full_name': 1, 'email': 1}):
        by_name.setdefault(norm(c.get('full_name')), []).append(c)

    out = []
    for file_name, sha in rows:
        docs = hash_map.get(sha) or []
        if docs:
            cand = candidates.get(docs[0]['candidate_id'])
            if cand:
                out.append((file_name, 'Sí (hash)', cand.get('full_name') or '—', cand['id'], cand.get('email') or ''))
            else:
                out.append((file_name, 'Hash sin ficha vigente', docs[0].get('candidate_name') or '—',
                            docs[0]['candidate_id'], ''))
            continue
        guess = name_from_file(file_name)
        matches = []
        if guess:
            tokens = [t for t in guess.split() if len(t) > 2]
            for key, people in by_name.items():
                if not key:
                    continue
                shared = sum(1 for t in tokens if t in key.split())
                if shared >= 2 or (tokens and key == guess):
                    matches.extend(people)
        if matches:
            unique = {m['id']: m for m in matches}.values()
            label = 'Probable (por nombre)'
            names = '; '.join(m['full_name'] for m in unique)
            ids = '; '.join(m['id'] for m in unique)
            emails = '; '.join(m.get('email') or '' for m in unique)
            out.append((file_name, label, names, ids, emails))
        else:
            out.append((file_name, 'No', '—', '', ''))

    width = max(len(f) for f, *_ in out) + 2
    print('\n' + 'ARCHIVO'.ljust(width) + '¿YA ESTÁ?'.ljust(24) + 'CANDIDATO')
    print('-' * (width + 60))
    for file_name, state, name, cid, _ in out:
        print(file_name.ljust(width) + state.ljust(24) + (name if name else '—'))

    counts = {}
    for _, state, *_ in out:
        counts[state] = counts.get(state, 0) + 1
    print('\nResumen:', counts)

    with open(OUT_PATH, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['archivo', 'ya_esta', 'candidato', 'candidate_id', 'email'])
        writer.writerows(out)
    print('Tabla completa en', OUT_PATH)


if __name__ == '__main__':
    asyncio.run(main())
