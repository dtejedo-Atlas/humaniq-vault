"""Option A browser fixture regression (MOCKED API writes; no shared Atlas mutations)."""

import asyncio
import json
from pathlib import Path
from dotenv import dotenv_values


async def check(page):
    base = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    candidate_id = "fixture-candidate-optiona"

    state = {
        "role": "admin",
        "user_id": "admin-1",
        "classify_status": 200,
        "classify_delay_ms": 0,
        "classify_calls": 0,
        "patch_status": 200,
        "patch_delay_ms": 0,
        "patch_calls": [],
        "assigned": False,
        "permission_status": 200,
        "permission_delay_ms": 0,
    }

    candidate = {
        "id": candidate_id,
        "full_name": "Candidato Nombre Extremadamente Largo Para Validación Responsive y Acciones Encabezado",
        "current_title": "Director Senior de Operaciones y Transformación Estratégica Regional",
        "current_company": "Empresa Internacional Muy Larga de Prueba S.A. de C.V.",
        "email": "correo.extenso.opcion.a.validacion+talent.vault@example-enterprise-domain.mx",
        "phone": "+52 5512345678",
        "city": "Ciudad de México",
        "state": "CDMX",
        "country": "México",
        "industry": "technology",
        "functional_area": "it",
        "seniority": "senior",
        "years_experience": None,
        "status": "reviewing",
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
        "skills": ["Liderazgo"],
        "languages": ["Español"],
        "tags": [],
        "previous_companies": [],
        "notes": [],
        "resume_files": [],
        "job_assignments": [],
        "ai_classification": {
            "industry": "technology",
            "functional_area": "it",
            "seniority": "senior",
            "years_experience": None,
            "confidence_score": 0.63,
            "approved_by_recruiter": False,
            "suggested_tags": [],
        },
    }

    async def route_api(route):
        req = route.request
        path = req.url.split('/api', 1)[1].split('?', 1)[0]
        method = req.method.upper()

        if path == "/auth/me":
            await route.fulfill(status=200, json={
                "id": state["user_id"], "name": "Admin", "email": "admin@example.com", "role": state["role"], "is_active": True,
            })
            return
        if path == f"/candidates/{candidate_id}/can-edit":
            if state["permission_delay_ms"]:
                await asyncio.sleep(state["permission_delay_ms"] / 1000)
            allowed = state["role"] in ("admin", "super_admin") or (state["role"] == "recruiter" and state["assigned"])
            await route.fulfill(status=state["permission_status"], json={"can_edit": allowed, "reason": None if allowed else "Sin permiso de edición", "user_role": state["role"], "assignments": []})
            return
        if path == f"/candidates/{candidate_id}" and method == "GET":
            await route.fulfill(status=200, json=candidate)
            return
        if path == f"/atlas/classify/{candidate_id}" and method == "POST":
            state["classify_calls"] += 1
            if state["classify_delay_ms"]:
                await asyncio.sleep(state["classify_delay_ms"] / 1000)
            if state["classify_status"] != 200:
                await route.fulfill(status=state["classify_status"], json={"detail": f"classify error {state['classify_status']}"})
                return
            candidate["ai_classification"].update({"industry": "finance", "functional_area": "operations", "seniority": "manager", "confidence_score": 0.8})
            await route.fulfill(status=200, json=candidate["ai_classification"])
            return
        if path == f"/atlas/classifications/manual/{candidate_id}" and method == "PATCH":
            if state["patch_delay_ms"]:
                await asyncio.sleep(state["patch_delay_ms"] / 1000)
            payload = req.post_data_json or {}
            state["patch_calls"].append(payload)
            if state["patch_status"] != 200:
                await route.fulfill(status=state["patch_status"], json={"detail": f"manual error {state['patch_status']}"})
                return
            for k, v in payload.items():
                candidate[k] = v
                candidate["ai_classification"][k] = v
            await route.fulfill(status=200, json={"candidate_id": candidate_id, "industry": candidate["industry"], "functional_area": candidate["functional_area"], "seniority": candidate["seniority"], "years_experience": candidate["years_experience"], "saved": True})
            return
        if path == f"/atlas/approve-classification/{candidate_id}" and method == "POST":
            await route.fulfill(status=200, json={"message": "approved"})
            return

        if path == "/taxonomy/industries":
            await route.fulfill(status=200, json=[{"key": "technology", "name_es": "Tecnología", "name_en": "Technology"}, {"key": "finance", "name_es": "Finanzas", "name_en": "Finance"}])
            return
        if path == "/taxonomy/functional-areas":
            await route.fulfill(status=200, json=[{"key": "it", "name_es": "TI", "name_en": "IT"}, {"key": "operations", "name_es": "Operaciones", "name_en": "Operations"}])
            return
        if path == "/taxonomy/lookup":
            await route.fulfill(status=200, json={"industries": {"technology": {"key": "technology", "name_es": "Tecnología", "name_en": "Technology"}, "finance": {"key": "finance", "name_es": "Finanzas", "name_en": "Finance"}}, "functional_areas": {"it": {"key": "it", "name_es": "TI", "name_en": "IT"}, "operations": {"key": "operations", "name_es": "Operaciones", "name_en": "Operations"}}})
            return
        if path == "/taxonomy/seniority-levels":
            await route.fulfill(status=200, json={"levels": {"junior": {"level": 1, "label": "Junior"}, "senior": {"level": 2, "label": "Senior"}, "manager": {"level": 3, "label": "Manager"}}})
            return

        if path == "/status-config":
            await route.fulfill(status=200, json={"transitions": {"reviewing": ["qualified"]}})
            return
        if "duplicates" in path:
            await route.fulfill(status=200, json={"active_duplicates": {"total": 0, "high_confidence": [], "medium_confidence": []}})
            return
        if path.endswith('/cv-versions'):
            await route.fulfill(status=200, json={"versions": []})
            return
        if path.endswith('/latest'):
            await route.fulfill(status=200, json={"batch_id": None})
            return

        if method == "GET":
            await route.fulfill(status=200, json=[])
            return
        await route.fulfill(status=409, json={"detail": "fixture blocked mutation"})

    await page.route("**/api/**", route_api)
    await page.goto(base)
    await page.evaluate("localStorage.setItem('atlas_token', 'fixture-token')")
    await page.goto(f"{base}/candidates/{candidate_id}")
    await page.wait_for_selector('[data-testid="candidate-detail-content"]', timeout=30000)

    # Classify duplicate click lock
    state["classify_calls"] = 0
    state["classify_delay_ms"] = 1200
    await page.get_by_test_id("classify-button").click(force=True)
    await page.wait_for_timeout(120)
    assert await page.get_by_test_id("classify-button").is_disabled() is True
    await page.get_by_test_id("classify-button").click(force=True)
    await page.wait_for_timeout(1500)
    assert state["classify_calls"] == 1
    assert "80%" in await page.get_by_test_id("candidate-classification-confidence").inner_text()
    state["classify_delay_ms"] = 0

    # Classify error states
    for code in [403, 429, 500]:
        state["classify_status"] = code
        await page.reload()
        await page.wait_for_selector('[data-testid="candidate-detail-content"]', timeout=30000)
        await page.get_by_test_id("classify-button").click(force=True)
        await page.wait_for_timeout(400)
        text = (await page.locator("body").inner_text()).lower()
        assert f"classify error {code}" in text
        assert "candidato clasificado por humaniq ia" not in text
    state["classify_status"] = 200

    candidate["ai_classification"].update({"industry": "technology", "functional_area": "it", "seniority": "senior", "confidence_score": 0.63})
    await page.reload()
    await page.get_by_test_id("candidate-classification-fields").wait_for(state="visible")
    await page.wait_for_timeout(300)

    # Exactly four manual dropdowns + field-only patch
    ids = [
        f"review-industry-{candidate_id}",
        f"review-functional_area-{candidate_id}",
        f"review-seniority-{candidate_id}",
        f"review-years_experience-{candidate_id}",
    ]
    for testid in ids:
        assert await page.get_by_test_id(testid).count() == 1

    await page.get_by_test_id(f"review-industry-{candidate_id}").click(force=True)
    await page.wait_for_timeout(200)
    await page.get_by_test_id(f"review-industry-{candidate_id}-option-finance").click(force=True)
    await page.wait_for_timeout(300)
    await page.get_by_test_id(f"review-functional_area-{candidate_id}").click(force=True)
    await page.wait_for_timeout(200)
    await page.get_by_test_id(f"review-functional_area-{candidate_id}-option-operations").click(force=True)
    await page.wait_for_timeout(300)
    await page.get_by_test_id(f"review-seniority-{candidate_id}").click(force=True)
    await page.wait_for_timeout(200)
    await page.get_by_test_id(f"review-seniority-{candidate_id}-option-manager").click(force=True)
    await page.wait_for_timeout(300)
    await page.get_by_test_id(f"review-years_experience-{candidate_id}").click(force=True)
    await page.wait_for_timeout(200)
    await page.get_by_test_id(f"review-years_experience-{candidate_id}-option-0").click(force=True)
    await page.wait_for_timeout(300)
    assert "0" in await page.get_by_test_id(f"review-years_experience-{candidate_id}").inner_text()
    await page.get_by_test_id(f"review-years_experience-{candidate_id}").click(force=True)
    await page.wait_for_timeout(200)
    await page.get_by_test_id(f"review-years_experience-{candidate_id}-unset").click(force=True)
    await page.wait_for_timeout(300)
    assert all(len(payload.keys()) == 1 for payload in state["patch_calls"])
    assert state["patch_calls"] == [{"industry": "finance"}, {"functional_area": "operations"}, {"seniority": "manager"}, {"years_experience": 0}, {"years_experience": None}]
    await page.reload()
    await page.get_by_test_id(ids[0]).wait_for(state="visible")
    await page.wait_for_timeout(300)
    assert "Finanzas" in await page.get_by_test_id(ids[0]).inner_text()
    assert "Operaciones" in await page.get_by_test_id(ids[1]).inner_text()
    assert "Manager" in await page.get_by_test_id(ids[2]).inner_text()
    assert "Sin dato" in await page.get_by_test_id(ids[3]).inner_text()
    assert "63%" in await page.get_by_test_id("candidate-classification-confidence").inner_text()

    # Lock classify/approve while save in-flight
    state["patch_delay_ms"] = 1200
    await page.get_by_test_id(f"review-industry-{candidate_id}").click(force=True)
    await page.wait_for_timeout(200)
    await page.get_by_test_id(f"review-industry-{candidate_id}-option-technology").click(force=True)
    await page.wait_for_timeout(100)
    assert await page.get_by_test_id("classify-button").is_disabled() is True
    assert await page.get_by_test_id("approve-classification-button").is_disabled() is True
    await page.wait_for_timeout(1400)
    state["patch_delay_ms"] = 0

    # Responsive widths
    responsive = []
    for width, height in [(320, 844), (768, 1024), (1024, 900), (1440, 900)]:
        await page.set_viewport_size({"width": width, "height": height})
        await page.wait_for_timeout(250)
        metrics = await page.evaluate("""() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth })""")
        responsive.append(metrics)
        assert metrics["scroll"] <= metrics["width"] + 1

    Path('/app/test_reports/option_a_mocked_responsive.json').write_text(json.dumps(responsive, indent=2), encoding='utf-8')
    print('PASS: clasificación, errores IA, cuatro PATCH individuales, recarga, cero/null, bloqueo y responsive', responsive)

    await page.set_viewport_size({"width": 1920, "height": 800})
    # Matrix must match server policy, not simply hide controls for every recruiter.
    for role, assigned, editable in [("admin", False, True), ("super_admin", False, True), ("recruiter", True, True), ("recruiter", False, False), ("researcher", True, False)]:
        state.update(role=role, assigned=assigned)
        await page.reload()
        await page.get_by_test_id(ids[0]).wait_for(state="visible")
        await page.wait_for_timeout(300)
        assert await page.get_by_test_id("classify-button").count() == (1 if role in ("admin", "super_admin") else 0)
        for testid in ids:
            assert await page.get_by_test_id(testid).is_disabled() == (not editable)
        print('PASS permisos:', role, 'asignado:', assigned, 'edición:', editable)

    state.update(role="admin", assigned=False)
    for code in [403, 409, 422, 500]:
        state["patch_status"] = code
        await page.reload()
        await page.get_by_test_id(ids[0]).wait_for(state="visible")
        await page.wait_for_timeout(300)
        old_value = await page.get_by_test_id(ids[0]).inner_text()
        await page.get_by_test_id(ids[0]).click(force=True)
        await page.get_by_test_id(ids[0] + '-option-finance').click(force=True)
        await page.get_by_test_id("candidate-classification-save-error").wait_for(state="visible")
        assert old_value == await page.get_by_test_id(ids[0]).inner_text()
        assert "Guardado" not in await page.get_by_test_id("candidate-classification-save-status").inner_text()
        assert await page.get_by_test_id(ids[0]).is_disabled() == (code in [403, 409])
        print('PASS error de guardado:', code, 'sin cambio ficticio')

    state["patch_status"] = 200
    state["permission_status"] = 500
    await page.reload()
    await page.get_by_test_id("candidate-readonly-notice").wait_for(state="visible")
    assert all([await page.get_by_test_id(testid).is_disabled() for testid in ids])
    print('PASS permisos no verificables: solo lectura')
    state.update(permission_status=200, permission_delay_ms=1500)
    await page.reload()
    await page.get_by_test_id(ids[0]).wait_for(state="visible")
    assert all([await page.get_by_test_id(testid).is_disabled() for testid in ids])
    await page.wait_for_timeout(1700)
    assert not await page.get_by_test_id(ids[0]).is_disabled()
    print('PASS permisos pendientes: sin ventana de edición')

    state["permission_delay_ms"] = 0
    candidate["ai_classification"]["approved_by_recruiter"] = True
    await page.reload()
    await page.get_by_test_id(ids[0]).wait_for(state="visible")
    await page.wait_for_timeout(300)
    assert all([await page.get_by_test_id(testid).is_disabled() for testid in ids])
    assert 'aprobada' in await page.get_by_test_id("candidate-classification-save-status").inner_text()
    print('PASS clasificación aprobada: bloqueo existente respetado')
