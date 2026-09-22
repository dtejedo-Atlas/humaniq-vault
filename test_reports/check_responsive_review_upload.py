"""Read-only browser regression after iteration_27 responsive fixes."""
import asyncio
import json
import re
from pathlib import Path
from dotenv import dotenv_values


async def check(page):
    base = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    section = Path('/app/memory/test_credentials.md').read_text().split('## Admin (testing)', 1)[1].split('\n## ', 1)[0]
    email = re.search(r'\*\*Email:\*\* (.+)', section).group(1).strip()
    password = re.search(r'\*\*Password:\*\* (.+)', section).group(1).strip()
    results = []
    if page:
        response = await page.request.post(base + '/api/auth/login', data={'email': email, 'password': password})
        assert response.status == 200
        token = (await response.json())['access_token']
        await page.goto(base)
        await page.evaluate('(token) => localStorage.setItem("atlas_token", token)', token)
        for route, marker in [('/review', 'review-candidate-52ad7b77-769c-4783-829e-62d8babf5322'), ('/upload', 'upload-dropzone')]:
            await page.goto(base + route)
            await page.get_by_test_id(marker).wait_for(state='visible', timeout=60000)
            if route == '/upload':
                await page.wait_for_function('!document.body.innerText.includes("Recuperando último lote")', timeout=30000)
            for width in [320, 768, 1024, 1440]:
                await page.set_viewport_size({'width': width, 'height': 800})
                await page.wait_for_timeout(200)
                metrics = await page.evaluate('''() => ({
                    viewport: window.innerWidth, scroll: document.documentElement.scrollWidth,
                    overflow: [...document.querySelectorAll('body *')].filter(el => {
                        const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
                        return r.width>0 && r.right>innerWidth+1 && s.visibility!=='hidden';
                    }).slice(0, 8).map(el => ({tag:el.tagName, testId:el.dataset.testid, classes:el.className}))
                })''')
                results.append({'route': route, 'width': width, **metrics})
                print(json.dumps(results[-1], ensure_ascii=False), flush=True)
                assert metrics['scroll'] <= width + 1
            await page.set_viewport_size({'width': 320, 'height': 800})
            await page.wait_for_timeout(250)
            await page.get_by_test_id('mobile-menu-toggle').click()
            await page.wait_for_timeout(250)
            assert await page.get_by_test_id('workspace-navigation').is_visible()
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(220)
            assert not await page.get_by_test_id('workspace-navigation').is_visible()
        await page.set_viewport_size({'width': 1920, 'height': 800})
    Path('/app/test_reports/responsive_review_upload_verified.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    from playwright.async_api import async_playwright

    async def main():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await check(page)
            await browser.close()

    asyncio.run(main())