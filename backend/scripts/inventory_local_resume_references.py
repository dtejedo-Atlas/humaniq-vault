"""Read-only inventory of stored CV references; never uploads, migrates or deletes data."""
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def classify_reference(value):
    if not isinstance(value, str) or not value.strip():
        return 'missing', None
    key = value.strip()
    if key.startswith('atlas-talent-vault/'):
        return 'remote', key
    local = (ROOT / key).resolve()
    if local.is_relative_to((ROOT / 'uploads').resolve()):
        return 'local', str(local.relative_to(ROOT))
    return 'other', key


async def inventory():
    # Use the application's existing connection without executing app startup/lifespan.
    from server import db, client

    refs, totals = [], Counter()
    candidate_states = {}
    try:
        async for candidate in db.candidates.find({}, {'_id': 0, 'id': 1, 'is_deleted': 1, 'resume_files': 1}):
            deleted = candidate.get('is_deleted') is True
            candidate_states[candidate['id']] = deleted
            totals['candidates_total'] += 1
            totals['candidates_deleted' if deleted else 'candidates_active'] += 1
            for resume in candidate.get('resume_files') or []:
                kind, key = classify_reference(resume.get('file_path'))
                totals[f'candidate_resume_references_{kind}'] += 1
                refs.append({'source': 'candidates', 'candidate_id': candidate['id'], 'deleted': deleted,
                             'kind': kind, 'key': key})
        async for version in db.cv_versions.find({}, {'_id': 0, 'id': 1, 'candidate_id': 1, 'file_key': 1, 'is_active': 1, 'is_current': 1}):
            kind, key = classify_reference(version.get('file_key'))
            totals[f'version_references_{kind}'] += 1
            refs.append({'source': 'cv_versions', 'version_id': version.get('id'),
                         'candidate_id': version.get('candidate_id'), 'kind': kind, 'key': key,
                         'is_current': version.get('is_current') is True, 'is_active': version.get('is_active') is True})
    finally:
        client.close()

    local = [ref for ref in refs if ref['kind'] == 'local']
    files = defaultdict(list)
    for ref in local:
        files[ref['key']].append(ref)
    active_candidates = {ref['candidate_id'] for ref in local if candidate_states.get(ref['candidate_id']) is False}
    current_active_keys = {ref['key'] for ref in local if ref['source'] == 'candidates' and not ref['deleted']
                          or ref['source'] == 'cv_versions' and ref['is_current'] and ref['is_active']
                          and candidate_states.get(ref['candidate_id']) is False}
    existing = [key for key in files if (ROOT / key).is_file()]
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'read_only': True, 'database_writes': 0, 'file_migrations': 0,
        'scope': 'All candidates including soft-deleted and all cv_versions; existing app database connection.',
        'counts': dict(totals),
        'local_unique_files': len(files),
        'local_references_total': len(local),
        'local_candidate_ids_total': len({ref['candidate_id'] for ref in local}),
        'active_candidates_with_local_references': len(active_candidates),
        'unique_local_files_in_active_candidate_or_current_active_version': len(current_active_keys),
        'local_files_present_in_preview': len(existing),
        'local_files_not_found_in_preview': len(files) - len(existing),
        'local_versions_without_candidate': sum(ref['source'] == 'cv_versions' and ref['candidate_id'] not in candidate_states for ref in local),
        'limitations': [
            'Counts local references, not proof of which historical upload branch created them.',
            'File existence checked only in this preview container, never production; missing here does not prove irrecoverable loss.',
            'Remote object availability and local file readability not checked; no CV contents were opened.',
        ],
    }
    private_dir = Path('/root/humaniq_cv_diagnosis')
    private_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_path = private_dir / 'local_resume_inventory.json'
    descriptor = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump({'report': report, 'local_references': local,
                   'other_references': [ref for ref in refs if ref['kind'] == 'other'],
                   'preview_file_presence': {key: (ROOT / key).is_file() for key in files}}, handle, indent=2)
    output = ROOT.parent / 'test_reports' / 'cv_local_inventory.json'
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(inventory())