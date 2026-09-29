#!/usr/bin/env python3
"""Fase 0: calcula SHA-256 de archivo y de texto normalizado para cada CV y los guarda en cv_hashes.

No modifica candidatos ni elimina nada. Solo lectura de object storage + escritura en cv_hashes.
Uso:  python cv_hash_backfill.py [--limit N] [--workers 8]
"""
import sys
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.db_connection import get_db
from storage_service import StorageService
from document_parser import DocumentParser
from text_utils import normalize_for_search

MIN_TEXT_LEN = 300


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def process(entry):
    candidate_id, cand_name, created_by, f = entry
    path = f.get('file_path')
    out = {
        'candidate_id': candidate_id,
        'candidate_name': cand_name,
        'file_path': path,
        'file_name': f.get('file_name'),
        'file_type': f.get('file_type'),
        'upload_date': f.get('upload_date'),
        'uploaded_by': f.get('uploaded_by') or created_by,
        'computed_at': datetime.now(timezone.utc).isoformat(),
    }
    try:
        data, content_type = StorageService.get_object(path)
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
        return out

    out['sha256_file'] = hash_bytes(data)
    out['size'] = len(data)

    try:
        text = DocumentParser.extract_text_from_bytes(data, f.get('file_type') or content_type)
    except Exception as e:
        text = ''
        out['text_error'] = f'{type(e).__name__}: {e}'

    norm = normalize_for_search(text or '')
    out['text_len'] = len(norm)
    out['sha256_text'] = hash_bytes(norm.encode()) if len(norm) >= MIN_TEXT_LEN else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()

    db = get_db()
    entries = []
    cursor = db.candidates.find(
        {'is_deleted': {'$ne': True}},
        {'_id': 0, 'id': 1, 'full_name': 1, 'created_by': 1, 'resume_files': 1}
    )
    for c in cursor:
        for f in (c.get('resume_files') or []):
            if f.get('file_path'):
                entries.append((c['id'], c.get('full_name'), c.get('created_by'), f))
    if args.limit:
        entries = entries[:args.limit]

    print(f'CVs a procesar: {len(entries)}', flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for res in pool.map(process, entries):
            db.cv_hashes.update_one(
                {'candidate_id': res['candidate_id'], 'file_path': res['file_path']},
                {'$set': res},
                upsert=True
            )
            done += 1
            if done % 25 == 0:
                print(f'  {done}/{len(entries)}', flush=True)

    errors = db.cv_hashes.count_documents({'error': {'$exists': True}})
    no_text = db.cv_hashes.count_documents({'sha256_text': None})
    print(f'Listo. Registros: {db.cv_hashes.count_documents({})} | errores descarga: {errors} | sin hash de texto (<{MIN_TEXT_LEN} chars): {no_text}')


if __name__ == '__main__':
    main()
