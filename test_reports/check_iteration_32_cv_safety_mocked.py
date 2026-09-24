import json
from urllib.parse import urlparse
from dotenv import dotenv_values


async def check(page):
    """Mocked frontend regression check for CV safety flows (iteration 32)."""
    base = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    state = {'classify_calls': 0, 'candidate_gets': 0, 'upload_calls': 0}

    async def route_handler(route):
        req = route.request
        url = req.url
        method = req.method
        path = urlparse(url).path

        async def ok(data, status=200):
            await route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

        if '/api/auth/login' in url and method == 'POST':
            return await ok({'access_token': 'fake-token', 'token_type': 'bearer', 'user': {'id': 'admin-1', 'email': 'admin@example.com', 'name': 'Admin', 'role': 'admin', 'is_active': True, 'created_at': '2026-01-01T00:00:00+00:00'}})
        if '/api/auth/me' in url and method == 'GET':
            return await ok({'id': 'admin-1', 'email': 'admin@example.com', 'name': 'Admin', 'role': 'admin', 'is_active': True, 'created_at': '2026-01-01T00:00:00+00:00'})

        if '/api/dashboard/stats' in url and method == 'GET':
            return await ok({'total_candidates': 1, 'active_jobs': 0, 'new_this_week': 0, 'avg_match_score': 0})
        if '/api/dashboard/recent-activity' in url and method == 'GET':
            return await ok([])
        if '/api/dashboard/operational' in url and method == 'GET':
            return await ok({'totals': {}, 'distributions': {}})

        if '/api/status-config' in url and method == 'GET':
            return await ok({'transitions': {'new': ['reviewing']}})
        if '/api/taxonomy/lookup' in url and method == 'GET':
            return await ok({'industries': {}, 'functional_areas': {}})
        if '/api/taxonomy/industries' in url and method == 'GET':
            return await ok([])
        if '/api/taxonomy/functional-areas' in url and method == 'GET':
            return await ok([])
        if '/api/taxonomy/seniority-levels' in url and method == 'GET':
            return await ok({'levels': {}})

        if path.endswith('/cv-versions'):
            return await ok({'versions': []})
        if path.endswith('/pending/count'):
            return await ok({'count': state['classify_calls']})

        if '/api/candidates/cand-1/can-edit' in url and method == 'GET':
            return await ok({'can_edit': True, 'reason': None, 'assignments': []})
        if '/api/candidates/cand-1/duplicates' in url and method == 'GET':
            return await ok({'active_duplicates': {'total': 0, 'high_confidence': [], 'medium_confidence': []}})
        if path == '/api/candidates/cand-1' and method == 'GET':
            state['candidate_gets'] += 1
            return await ok({'id': 'cand-1', 'full_name': 'Candidato Mock', 'country': 'México', 'status': 'new', 'notes': [], 'tags': [], 'skills': [], 'languages': [], 'job_assignments': [], 'resume_files': [], 'review_status': 'manual_capture' if state['classify_calls'] else 'pending_review', 'review_message': 'Requiere captura manual. CV ilegible para clasificación.', 'cv_storage_issue': {'status': 'failed', 'file_name': 'cv.pdf', 'message': 'No se pudo confirmar el guardado remoto del CV original. Vuelve a subir el archivo.'}, 'ai_classification': None if state['classify_calls'] else {'confidence_score': 0.88, 'approved_by_recruiter': False}, 'created_at': '2026-01-01T00:00:00+00:00', 'updated_at': '2026-01-01T00:00:00+00:00'})
        if '/api/atlas/classify/cand-1' in url and method == 'POST':
            state['classify_calls'] += 1
            return await ok({'detail': 'Requiere captura manual. CV ilegible para clasificación.'}, status=422)

        if path == '/api/candidates/upload-resume' and method == 'POST':
            state['upload_calls'] += 1
            message = 'No se pudo confirmar el guardado remoto del CV original. La ficha se conserva; vuelve a subir el archivo.'
            return await ok({'status': 'failed', 'candidate_id': 'cand-1', 'message': message, 'stage_reached': 'storage',
                             'extracted_name': 'Candidato Mock', 'errors': [{'type': 'storage_upload_failed', 'stage': 'storage', 'message': message}],
                             'warnings': [], 'cv_storage_issue': {'status': 'failed', 'message': message}})

        if '/api/candidates/upload-batches/latest' in url and method == 'GET':
            return await ok({'batch_id': 'batch-1'})
        if '/api/candidates/batch/batch-1' in url and method == 'GET':
            return await ok({'batch_id': 'batch-1', 'total_files': 1, 'is_complete': True, 'stats': {'pending': 0, 'processing': 0, 'completed': 0, 'partial': 0, 'failed': 1, 'rejected': 0}, 'jobs': [{'job_id': 'job-1', 'file_name': 'broken.pdf', 'status': 'failed', 'progress': 100, 'current_stage': 'storage', 'candidate_id': 'cand-1', 'errors': [{'type': 'storage_upload_failed', 'stage': 'storage', 'message': 'No se pudo confirmar el guardado remoto del CV original.'}], 'warnings': []}], 'rejected_files': []})

        if path.startswith('/api/'):
            return await ok([] if method == 'GET' else {'detail': 'Unexpected mutation blocked by fixture'}, 200 if method == 'GET' else 409)
        return await route.continue_()

    await page.route('**/*', route_handler)
    await page.set_viewport_size({"width": 1920, "height": 800})
    await page.add_init_script('localStorage.setItem("atlas_token", "cv-safety-fixture-token")')

    await page.goto(base + '/candidates/cand-1', wait_until='domcontentloaded')
    await page.get_by_test_id('classify-button').wait_for(state='visible', timeout=15000)
    await page.click('[data-testid="classify-button"]', force=True)
    await page.get_by_test_id('candidate-manual-capture-alert').wait_for(state='visible', timeout=10000)
    assert state['classify_calls'] == 1 and state['candidate_gets'] >= 2
    assert await page.get_by_test_id('approve-classification-button').count() == 0
    assert 'Candidato clasificado por Humaniq IA' not in await page.locator('body').inner_text()
    print('PASS: classify422 actualiza ficha y captura manual, sin éxito ni aprobación falsos')

    for width, height in [(320, 844), (768, 1024), (1024, 900), (1440, 900)]:
        await page.set_viewport_size({"width": width, "height": height})
        await page.wait_for_timeout(200)
        assert await page.locator('[data-testid="candidate-cv-storage-error"]').first.is_visible()
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    print('PASS: alertas sin desbordamiento en 320/768/1024/1440')

    await page.set_viewport_size({"width": 1440, "height": 900})
    await page.goto(base + '/upload', wait_until='domcontentloaded')
    await page.wait_for_selector('[data-testid="batch-failed-count"]', timeout=10000)
    await page.click('[data-testid="batch-job-expand-job-1"]', force=True)
    await page.wait_for_timeout(200)
    assert await page.locator('[data-testid="batch-storage-profile-job-1"]').first.is_visible()
    assert await page.locator('[data-testid="batch-job-retry-job-1"]').count() == 0
    print('PASS: lote fallido visible con acceso a ficha y sin reintento imposible')

    await page.get_by_test_id('upload-batch-mode').click(force=True)
    await page.get_by_test_id('upload-file-input').set_input_files({'name': 'synthetic-cv.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.4 SYNTHETIC FIXTURE ONLY'})
    await page.get_by_test_id('upload-result-storage-error-0').wait_for(state='visible', timeout=15000)
    assert state['upload_calls'] == 1
    assert 'Fallido' in await page.get_by_test_id('upload-result-0').inner_text()
    print('PASS: carga individual muestra error y original pendiente, no éxito')
