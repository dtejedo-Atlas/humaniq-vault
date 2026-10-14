"""Export del shortlist: mismo orden que la pantalla, sin puntuación ni markdown, fecha en español."""
import asyncio
import os
import re
import sys
from datetime import date

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
import export_service as es  # noqa: E402

JOB_ID = sys.argv[1] if len(sys.argv) > 1 else 'a5a9ceb5-6a43-4547-bd30-7966a96959b5'
PDF = sys.argv[2] if len(sys.argv) > 2 else None
results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


# Helpers
check('fecha en español sin locale', es.spanish_date(date(2026, 10, 12)) == '12 de octubre de 2026',
      es.spanish_date(date(2026, 10, 12)))
check('limpia markdown y encabezado repetido',
      es.clean_markdown('# Resumen Profesional Ejecutivo\n**Ana** es *líder*') == 'Ana es líder',
      es.clean_markdown('# Resumen Profesional Ejecutivo\n**Ana** es *líder*'))
largo = 'Primera oración completa que describe el rol. ' * 8
check('corta en oración completa, no a media palabra', es.trim_to_sentence(largo).endswith('.'),
      es.trim_to_sentence(largo)[-40:])
check('no supera el máximo de caracteres', len(es.trim_to_sentence(largo)) <= 301, str(len(es.trim_to_sentence(largo))))
check('títulos en mayúsculas pasan a formato título',
      es.title_case_if_shouting('SUBDIRECTOR COMERCIAL') == 'Subdirector Comercial',
      es.title_case_if_shouting('SUBDIRECTOR COMERCIAL'))
hoy = date(2026, 10, 13)
exp = es.recent_experience({'previous_companies': [
    {'company_name': 'Nueva', 'title': 'DIRECTOR', 'start_date': '2020-01', 'end_date': None,
     'description': 'Uno. Dos. ' + 'x' * 400},
    {'company_name': 'Vieja', 'title': 'Analista', 'start_date': '1998-01', 'end_date': '2002-01'},
]}, hoy)
check('solo empleos de los últimos 10 años', [e['company_name'] for e in exp] == ['Nueva'], str(exp))
check('descripción recortada por oración', len(exp[0]['description']) <= 301)
check('título del empleo en formato título', exp[0]['title'] == 'Director', exp[0]['title'])


async def main():
    db = AsyncIOMotorClient(os.environ['ATLAS_URI'])[os.environ['ATLAS_DB_NAME']]
    service = es.create_export_service(db)

    # Mismo orden que la pantalla
    snap = await db.job_match_snapshots.find_one({'job_id': JOB_ID, 'engine': 'unified'}, {'_id': 0})
    screen = [r['candidate_id'] for r in (snap['payload']['results'])][:15]
    matches = await service.get_job_matches(JOB_ID, limit=15, engine='unified')
    check('el export usa el mismo orden del ranking unificado',
          [m['candidate_id'] for m in matches] == screen,
          f"{[m['candidate_id'] for m in matches][:3]} vs {screen[:3]}")
    check('la puntuación del export es la final del motor único',
          matches[0]['match_percentage'] == snap['payload']['results'][0]['final_score'],
          f"{matches[0]['match_percentage']} vs {snap['payload']['results'][0]['final_score']}")
    check('nunca repite a la misma persona',
          len({m['candidate_id'] for m in matches}) == len(matches))

    # Sin ranking calculado pide generarlo en vez de recalcular
    con_snapshot = await db.job_match_snapshots.distinct('job_id', {'engine': 'unified'})
    sin_ranking = await db.jobs.find_one({'id': {'$nin': con_snapshot}}, {'_id': 0, 'id': 1})
    try:
        await service.get_job_matches(sin_ranking['id'], limit=5, engine='unified')
        check('sin ranking pide generarlo', False)
    except ValueError as error:
        check('sin ranking pide generarlo', 'Actualizar ranking' in str(error), str(error)[:60])
    except Exception:
        check('sin ranking pide generarlo', False)

    if PDF and os.path.exists(PDF):
        text = '\n'.join((page.extract_text() or '') for page in PdfReader(PDF).pages)
        check('PDF sin "HMS"', 'HMS' not in text)
        check('PDF sin "BACKUP"', 'BACKUP' not in text.upper())
        check('PDF sin markdown "**"', '**' not in text)
        check('PDF sin encabezados "#"', '#' not in text)
        check('PDF con fecha en español', bool(re.search(r'\d{1,2} de [a-záéíóú]+ de 20\d\d', text)),
              (re.search(r'\d{1,2} de \w+ de 20\d\d', text) or [''])[0] if re.search(r'\d{1,2} de \w+ de 20\d\d', text) else 'no encontrada')
        # Aparece en el índice de portada y en su página: nunca como dos personas distintas
        luis = len(re.findall(r'Luis\s+L[oó]pez', text))
        check('Luis López aparece una sola vez como persona',
              luis <= 2 and 'Luis Lopez Cruz' not in text, f'{luis} menciones (portada + ficha)')
        check('PDF sin acción recomendada', 'Entrevistar' not in text and 'Prioridad baja' not in text)



if __name__ == '__main__':
    asyncio.run(main())
    print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
    sys.exit(0 if all(ok for _, ok in results) else 1)
