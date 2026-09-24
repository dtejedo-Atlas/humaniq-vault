"""Browser-only fixture regression: all API traffic intercepted, no production writes."""
import json
from pathlib import Path
from dotenv import dotenv_values


async def check(page):
    base = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    user = {'id': 'fixture-admin', 'name': 'Admin de prueba', 'email': 'fixture@example.com', 'role': 'admin', 'is_active': True}
    candidate = {
        'id': 'fixture-candidate', 'full_name': 'Candidato de prueba con un nombre extenso para verificar la ficha',
        'current_title': 'Responsable de proyectos y operaciones', 'current_company': 'Empresa de prueba',
        'email': 'correo.extenso.para.verificacion@example.com', 'phone': '+52 5555555555', 'city': 'Ciudad de México', 'country': 'México',
        'years_experience': 8, 'seniority': 'senior', 'industry': 'technology', 'functional_area': 'it', 'status': 'active',
        'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
        'skills': ['Coordinación de proyectos y equipos multidisciplinarios'], 'languages': ['Español'], 'tags': [],
        'previous_companies': [], 'education': [], 'job_assignments': [],
        'notes': [{'id': 'fixture-note', 'note': 'Nota compartida de prueba. ' * 12, 'created_by': user['name'], 'created_by_id': user['id'], 'created_at': '2026-01-01T00:00:00Z'}],
        'resume_files': [{'id': 'fixture-resume', 'file_name': 'CV de prueba.pdf', 'file_path': 'fixture.pdf', 'file_type': 'application/pdf', 'upload_date': '2026-01-01T00:00:00Z'}],
        'ai_classification': {'industry': 'technology', 'functional_area': 'it', 'seniority': 'senior', 'confidence_score': .6, 'suggested_tags': [], 'approved_by_recruiter': False},
    }

    async def route_api(route):
        path = route.request.url.split('/api', 1)[1].split('?', 1)[0]
        if route.request.method not in ('GET', 'OPTIONS'):
            await route.fulfill(status=409, json={'detail': 'Read-only responsive fixture'})
            return
        if path == '/auth/me': payload = user
        elif path == '/candidates/fixture-candidate': payload = candidate
        elif path.endswith('/can-edit'): payload = {'can_edit': True, 'user_role': 'admin', 'reason': None, 'assignments': []}
        elif path == '/taxonomy/lookup': payload = {'industries': {}, 'functional_areas': {}}
        elif path == '/taxonomy/seniority-levels': payload = {'levels': {}}
        elif path == '/status-config': payload = {'transitions': {}}
        elif 'duplicates' in path: payload = {'active_duplicates': {'total': 0, 'high_confidence': [], 'medium_confidence': []}}
        elif path.endswith('/cv-versions'): payload = {'versions': []}
        elif 'latest' in path: payload = {'batch_id': None}
        elif path.endswith('/count'): payload = {'count': 0}
        elif path == '/users': payload = {'users': []}
        elif 'assignments' in path: payload = {'assignments': []}
        elif path.endswith('/notes'): payload = {'notes': candidate['notes'], 'notes_count': 1}
        else: payload = []
        await route.fulfill(status=200, json=payload)

    await page.route('**/api/**', route_api)
    await page.goto(base)
    await page.evaluate('localStorage.setItem("atlas_token", "fixture-only-token")')
    await page.goto(base + '/candidates/fixture-candidate')
    await page.get_by_test_id('classify-button').wait_for(state='visible', timeout=30000)
    results = []
    for width in [320, 768, 1024, 1440]:
        await page.set_viewport_size({'width': width, 'height': 800})
        await page.wait_for_timeout(250)
        metrics = await page.evaluate('''() => ({scroll:document.documentElement.scrollWidth, viewport:innerWidth,
            offenders:[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.right>innerWidth+1&&getComputedStyle(el).visibility!=='hidden'}).slice(0,8).map(el=>({tag:el.tagName,id:el.dataset.testid,classes:el.className}))})''')
        print(width, json.dumps(metrics)); results.append({'width': width, **metrics})
        assert metrics['scroll'] <= width + 1
    # Option A is limited to classification/profile layout; note deletion is outside scope.
    await page.set_viewport_size({'width': 1920, 'height': 800})
    Path('/app/test_reports/security_candidate_responsive_verified.json').write_text(json.dumps(results, indent=2))