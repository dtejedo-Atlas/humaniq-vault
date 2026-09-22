"""Explicit, resumable Layer-1 operation on the 34 authorized diagnostic IDs only.

Uses unchanged first-pass Atlas methods. No uploads, deletes, approvals, embeddings,
summaries or matching. Complete before-images are retained in Mongo for traceability.
"""
import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.db_connection import get_db
from document_parser import DocumentParser
from pdf_extraction import EXTRACTION_VERSION
from atlas_service import AtlasAIService
from taxonomy import get_industry_by_key, get_functional_area_by_key
from models import Candidate, AIClassification, SeniorityLevel

PARSED_FIELDS = ('full_name', 'email', 'phone', 'city', 'state', 'country', 'linkedin_url',
                 'current_company', 'current_title', 'years_experience', 'skills', 'languages', 'cv_language', 'previous_companies')


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    evidence_path = Path(args.evidence)
    evidence = json.loads(evidence_path.read_text())
    assert len(evidence['candidates']) == 34
    db, ai = get_db(), AtlasAIService()
    semaphore = asyncio.Semaphore(2)
    output = []

    async def process(row):
        async with semaphore:
            cid = row['id']
            before = db.candidates.find_one({'id': cid, 'is_deleted': {'$ne': True}}, {'_id': 0})
            assert before is not None, 'Authorized candidate unavailable'
            raw = Path(row['local_path']).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            assert sha == row['sha256'], 'Original diagnostic file changed'
            source_refs = lambda document: [(item.get('file_path'), item.get('file_name')) for item in document.get('resume_files', [])]
            assert source_refs(before) == source_refs(row['detail']), 'CV version changed since diagnosis'
            run_id = f'layer1:{EXTRACTION_VERSION}:{cid}:{sha}'
            prior = db.cv_reprocessing_runs.find_one({'run_id': run_id, 'status': 'completed'}, {'_id': 0})
            if args.apply and prior:
                output.append(prior['result']); print(json.dumps(prior['result'], ensure_ascii=False), flush=True); return
            extraction = await asyncio.to_thread(DocumentParser.extract_with_details, raw, row['format'])
            result = {'id': cid, 'name': row['full_name'], 'text_chars': extraction['text_chars'], 'readable': extraction['readable'],
                      'ocr_pages': sum(p['ocr_attempted'] for p in extraction['pages']), 'ocr_failed_pages': sum(p['ocr_failed'] for p in extraction['pages'])}
            if not args.apply:
                result['classification_not_run'] = True
            elif not extraction['readable']:
                result['auto_classified'] = False
            else:
                db.cv_reprocessing_runs.update_one({'run_id': run_id}, {'$setOnInsert': {
                    'run_id': run_id, 'candidate_id': cid, 'before': before, 'created_at': datetime.now(timezone.utc).isoformat(),
                }, '$set': {'status': 'running', 'extraction': extraction}}, upsert=True)
                try:
                    parsed = await asyncio.wait_for(ai.parse_resume(extraction['text']), timeout=180)
                    if parsed.get('error'):
                        raise ValueError(parsed['error'])
                    # Validate normal parser fields without replacing the complete candidate document.
                    merged = {**before, **{key: value for key, value in parsed.items() if key in PARSED_FIELDS and value is not None}}
                    validated = Candidate.model_validate(merged).model_dump(mode='json')
                    classification = await asyncio.wait_for(ai.classify_candidate(parsed, extraction['text']), timeout=180)
                    validated_ai = AIClassification.model_validate(classification).model_dump(mode='json')
                    manual = (before.get('ai_classification') or {}).get('manual_fields', {})
                    updates = {key: validated[key] for key in PARSED_FIELDS if key in parsed and parsed[key] is not None and key not in manual}
                    for key in ('industry', 'functional_area', 'seniority'):
                        updates[key] = manual[key] if key in manual else validated_ai.get(key)
                        validated_ai[key] = updates[key]
                    validated_ai.update({'source': 'atlas_ai_extraction_reprocess', 'reasoning': classification.get('reasoning'), 'manual_fields': manual})
                    for key in ('approved_by_recruiter', 'approved_at', 'approved_by'):
                        if (before.get('ai_classification') or {}).get(key):
                            validated_ai[key] = before['ai_classification'][key]
                    updates.update({'ai_classification': validated_ai, 'cv_extraction': {key: val for key, val in extraction.items() if key != 'text'},
                                    'updated_at': datetime.now(timezone.utc).isoformat()})
                    condition = {'id': cid, 'updated_at': before.get('updated_at'), 'is_deleted': {'$ne': True}}
                    saved = db.candidates.update_one(condition, {'$set': updates})
                    if saved.matched_count != 1:
                        raise ValueError('Candidate changed concurrently; result retained, not applied')
                    result.update({key: updates.get(key, before.get(key)) for key in ('industry', 'functional_area', 'seniority', 'years_experience')})
                    result['confidence'] = validated_ai['confidence_score']
                    canonical = bool(get_industry_by_key(result['industry']) and get_functional_area_by_key(result['functional_area'])
                                     and result['seniority'] in {item.value for item in SeniorityLevel})
                    result['auto_classified'] = canonical and result['confidence'] >= .75
                    result['all_key_fields_complete'] = result['auto_classified'] and result['years_experience'] is not None
                    after = db.candidates.find_one({'id': cid}, {'_id': 0})
                    for key in set(before) - set(updates):
                        assert before[key] == after.get(key), f'Unexpected change to preserved field {key}'
                    db.cv_reprocessing_runs.update_one({'run_id': run_id}, {'$set': {'status': 'completed', 'result': result, 'parsed': parsed, 'classification': classification}})
                except Exception as error:
                    result.update({'error': str(error), 'auto_classified': False})
                    db.cv_reprocessing_runs.update_one({'run_id': run_id}, {'$set': {'status': 'failed', 'result': result}})
            output.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            destination = evidence_path.parent / ('layer1_results.json' if args.apply else 'layer1_extraction.json')
            destination.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    await asyncio.gather(*(process(row) for row in evidence['candidates']))
    summary = {'total': len(output), 'readable': sum(row['readable'] for row in output), 'unreadable': sum(not row['readable'] for row in output),
               'auto_classified': sum(row.get('auto_classified', False) for row in output), 'all_key_fields_complete': sum(row.get('all_key_fields_complete', False) for row in output),
               'errors': sum('error' in row for row in output)}
    print('SUMMARY', json.dumps(summary), flush=True)


if __name__ == '__main__':
    asyncio.run(main())