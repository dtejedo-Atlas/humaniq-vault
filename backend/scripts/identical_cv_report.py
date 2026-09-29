#!/usr/bin/env python3
"""Fase 0: informe de grupos de CV identicos (sin eliminar nada).

Idéntico = mismo sha256_file O mismo sha256_text (texto normalizado >= 300 chars).
Clasifica cada grupo en:
  - safe: sobrantes sin notas/asignaciones/historial propio -> se puede eliminar sobrantes
  - merge_required: algun sobrante tiene datos propios -> flujo N-a-1
  - manual_review: el grupo contiene nombres distintos (posible error de carga)
"""
import sys
import json
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db_connection import get_db
from text_utils import normalize_for_search


def build_groups(db):
    rows = list(db.cv_hashes.find({'error': {'$exists': False}}, {'_id': 0}))
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for r in rows:
        parent.setdefault(r['file_path'], r['file_path'])

    by_file = defaultdict(list)
    by_text = defaultdict(list)
    for r in rows:
        by_file[r['sha256_file']].append(r['file_path'])
        if r.get('sha256_text'):
            by_text[r['sha256_text']].append(r['file_path'])

    for bucket in list(by_file.values()) + list(by_text.values()):
        for p in bucket[1:]:
            union(bucket[0], p)

    groups = defaultdict(list)
    index = {r['file_path']: r for r in rows}
    for r in rows:
        groups[find(r['file_path'])].append(r)
    return groups, index


def main():
    db = get_db()
    groups, _ = build_groups(db)

    candidates = {c['id']: c for c in db.candidates.find({'is_deleted': {'$ne': True}}, {'_id': 0})}
    users = {u['id']: u.get('name') or u.get('email') for u in db.users.find({}, {'_id': 0, 'id': 1, 'name': 1, 'email': 1})}

    assignment_counts = defaultdict(int)
    for a in db.assignments.find({}, {'_id': 0, 'candidate_id': 1}):
        assignment_counts[a.get('candidate_id')] += 1
    version_counts = defaultdict(int)
    for v in db.cv_versions.find({}, {'_id': 0, 'candidate_id': 1}):
        version_counts[v.get('candidate_id')] += 1

    report = []
    for key, rows in groups.items():
        cand_ids = sorted({r['candidate_id'] for r in rows})
        if len(cand_ids) < 2:
            continue
        members = []
        for cid in cand_ids:
            c = candidates.get(cid)
            if not c:
                continue
            notes = c.get('notes')
            note_count = len(notes) if isinstance(notes, list) else (1 if notes else 0)
            files = [r for r in rows if r['candidate_id'] == cid]
            members.append({
                'candidate_id': cid,
                'name': c.get('full_name'),
                'name_norm': normalize_for_search(c.get('full_name') or ''),
                'created_at': c.get('created_at'),
                'uploaded_by': users.get(c.get('created_by'), c.get('created_by')),
                'upload_date': min([f.get('upload_date') or '' for f in files]) or None,
                'file_names': [f.get('file_name') for f in files],
                'notes': note_count,
                'assignments': assignment_counts.get(cid, 0),
                'cv_versions': version_counts.get(cid, 0),
                'resume_files': len(c.get('resume_files') or []),
            })
        if len(members) < 2:
            continue
        members.sort(key=lambda m: m['created_at'] or '')
        keep, extras = members[0], members[1:]
        base = members[0]['name_norm']
        distinct_names = any(
            SequenceMatcher(None, base, m['name_norm']).ratio() < 0.6 for m in members[1:]
        )
        needs_merge = any(m['notes'] or m['assignments'] or m['cv_versions'] or m['resume_files'] > 1 for m in extras)
        if distinct_names:
            status = 'manual_review'
        elif needs_merge:
            status = 'merge_required'
        else:
            status = 'safe'
        report.append({
            'group_key': key,
            'status': status,
            'keep': keep,
            'extras': extras,
            'match': 'file' if len({r['sha256_file'] for r in rows}) == 1 else 'text',
        })

    report.sort(key=lambda g: (g['status'], -len(g['extras'])))
    out = Path('/app/test_reports/identical_cv_groups.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    by_status = defaultdict(lambda: [0, 0])
    for g in report:
        by_status[g['status']][0] += 1
        by_status[g['status']][1] += len(g['extras'])

    print(f'\nGrupos con CV identico: {len(report)}')
    print(f'{"estado":16} {"grupos":>7} {"fichas sobrantes":>17}')
    for st in ('safe', 'merge_required', 'manual_review'):
        g, e = by_status[st]
        print(f'{st:16} {g:>7} {e:>17}')
    total_extras = sum(len(g["extras"]) for g in report)
    print(f'{"TOTAL":16} {len(report):>7} {total_extras:>17}')
    print(f'\nDetalle: {out}')


if __name__ == '__main__':
    main()
