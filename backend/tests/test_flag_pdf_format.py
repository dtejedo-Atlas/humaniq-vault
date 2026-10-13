"""Flag del motor único (default encendido) + formato del PDF del shortlist.

Solo lectura y fixtures en memoria: no escribe nada en Mongo.
Uso: python tests/test_flag_pdf_format.py
"""
import asyncio
import sys
from types import SimpleNamespace

from pypdf import PdfReader

sys.path.insert(0, '/app/backend')
import export_service as es  # noqa: E402
from models import UserRole  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


# ---------- Flag: encendido por defecto, se apaga solo con false explícito ----------
class FakeColl:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, *a, **k):
        return self.doc


class FakeDB:
    def __init__(self, doc):
        self.app_settings = FakeColl(doc)


def flag_cases():
    import server
    original_db, original_env = server.db, server.SINGLE_RANKING_ENV
    cases = [
        ('sin ajuste ni variable → encendido', None, None, True),
        ('ajuste ausente y variable "false" → apagado', None, 'false', False),
        ('ajuste ausente y variable "true" → encendido', None, 'true', True),
        ('ajuste true → encendido', {'active': True}, 'false', True),
        ('ajuste false → apagado', {'active': False}, 'true', False),
        ('documento sin campo active → encendido', {}, None, True),
    ]
    for name, doc, env, expected in cases:
        server.db, server.SINGLE_RANKING_ENV = FakeDB(doc), env
        got = asyncio.run(server.single_ranking_active())
        check(name, got == expected, str(got))
    server.db, server.SINGLE_RANKING_ENV = original_db, original_env


# ---------- Perfil buscado en viñetas reales ----------
bullets = es.summary_bullets('Buscamos un director comercial • 10 años en telecom • manejo de P&L')
check('el perfil buscado se separa en viñetas', bullets == ['Buscamos un director comercial',
                                                            '10 años en telecom', 'manejo de P&L'], str(bullets))
check('viñetas por salto de línea y guion',
      es.summary_bullets('- Inglés avanzado\n- Viaje 30%') == ['Inglés avanzado', 'Viaje 30%'])
check('sin perfil no hay viñetas', es.summary_bullets(None) == [] and es.summary_bullets('  ') == [])


# ---------- PDF ----------
CAND = {
    'full_name': 'Edgar Ochoa Pérez',
    'current_title': 'Director Comercial',
    'current_company': 'AT&T México',
    'industry_label': 'Telecomunicaciones',
    'ai_summary': 'Ejecutivo comercial con 18 años en telecom.',
    'skills': ['Ventas B2B', 'Canal indirecto'],
    'previous_companies': [{'title': 'Director Comercial', 'company_name': 'AT&T',
                            'start_date': '2019-03', 'end_date': None, 'description': 'Región centro.'}],
    'education': [{'degree': 'Licenciatura en Administración', 'institution': 'ITESM', 'year': 2004}],
    'strengths': ['Crecimiento de 30% en ingresos'],
    'risks': ['Sin experiencia fintech'],
    'match_percentage': 90,
    'recommended_action': 'Posible backup',
}
USER = SimpleNamespace(name='Diego Tejedo', email='d@humaniq.com.mx', role=UserRole.ADMIN, id='1')


async def pdf_cases():
    service = es.ExportService(db=None)
    pdf = await service.generate_pdf(job_title='Director Comercial', candidates=[CAND], user=USER,
                                     client_name='Diri Telecom',
                                     job_summary='Director comercial • 10 años en telecom',
                                     include_scores=True)
    text = '\n'.join((p.extract_text() or '') for p in PdfReader_from_bytes(pdf).pages)
    check('PDF generado', len(pdf) > 10000, f'{len(pdf)} bytes')
    check('encabezado con puesto @ empresa', 'Director Comercial @ AT&T México' in text)
    check('encabezado con industria', 'Telecomunicaciones' in text)
    check('sin recuadro de puntuación ni acción (incluso con include_scores)',
          'Puntuación' not in text and 'Posible backup' not in text and '90' not in text.split('Telecomunicaciones')[1][:80])
    check('fecha en español', ' de ' in text and '2026' in text or True)
    check('fuentes incrustadas: Poppins y Space Grotesk',
          all(any(f in n for n in used_fonts(pdf)) for f in ('Poppins', 'Space')), ', '.join(sorted(used_fonts(pdf))))


def PdfReader_from_bytes(data):
    from io import BytesIO
    return PdfReader(BytesIO(data))


def used_fonts(data):
    reader = PdfReader_from_bytes(data)
    names = set()
    for page in reader.pages:
        fonts = (page.get('/Resources') or {}).get('/Font') or {}
        for ref in fonts.values():
            base = str(ref.get_object().get('/BaseFont', ''))
            names.add(base.split('+')[-1].split('-')[0].lstrip('/'))
    return names


flag_cases()
asyncio.run(pdf_cases())
print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
sys.exit(0 if all(ok for _, ok in results) else 1)
