"""Motor único: puntuación final 0.75·HMS + 0.25·fit, orden, acciones y alerta de discrepancia."""
import sys

from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from ai_refine_service import AIRefineService  # noqa: E402
from ai_fit_service import final_score  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


def row(cid, hms, name=None):
    return {"candidate_id": cid, "candidate_name": name or cid, "match_score_v3": hms,
            "knockout_results": {"K": 1.0, "results": [], "summary": ""}, "component_breakdown": {}}


# Aritmética de la puntuación final
check('0.75·HMS + 0.25·fit', final_score(56, 35) == 51, str(final_score(56, 35)))
check('sin fit evaluado la final es el HMS', final_score(72, None) == 72)
check('fit alto sube la final', final_score(60, 90) == 68, str(final_score(60, 90)))

# Sin fits, el comportamiento es idéntico al anterior (HMS manda)
v3 = [row('a', 70), row('b', 60), row('c', 50)]
rows = AIRefineService.unify(v3, [], set(), None)
check('sin fits conserva el orden del HMS', [r['candidate_id'] for r in rows] == ['a', 'b', 'c'])
check('sin fits final = HMS', all(r['final_score'] == r['match_score_v3'] for r in rows))
check('sin fits no hay alerta', all(r['ai_warning'] is None for r in rows))

# Con fits, el fit reordena y la calidad sale de la puntuación final
fits = {
    'a': {'fit': 20, 'why': 'es director de operaciones de TI, no comercial', 'strengths': [], 'risks': ['sin cuota comercial'],
          'evidence_verified': True},
    'b': {'fit': 95, 'why': 'dirigió la función comercial en telecom con cuota', 'strengths': [{'text': 'cuota', 'quote': 'cuota'}],
          'risks': [], 'evidence_verified': True},
    'c': {'fit': 85, 'why': 'ventas B2B en telecom', 'strengths': [], 'risks': [], 'evidence_verified': True},
}
rows = AIRefineService.unify(v3, [], set(), fits, True)
by_id = {r['candidate_id']: r for r in rows}
check('el fit reordena la lista', [r['candidate_id'] for r in rows] == ['b', 'c', 'a'],
      str([(r['candidate_id'], r['final_score']) for r in rows]))
check('final de a = 0.75·70 + 0.25·20', by_id['a']['final_score'] == 58, str(by_id['a']['final_score']))
check('final de b = 0.75·60 + 0.25·95', by_id['b']['final_score'] == 69, str(by_id['b']['final_score']))
check('calidad desde la puntuación final', by_id['b']['quality'] == 'bueno' and by_id['a']['quality'] == 'aceptable',
      f"{by_id['b']['quality']}/{by_id['a']['quality']}")
check('alerta de discrepancia cuando la IA no confirma',
      by_id['a']['ai_warning'] and 'no confirma' in by_id['a']['ai_warning'], str(by_id['a']['ai_warning']))
check('sin alerta cuando la IA confirma', by_id['b']['ai_warning'] is None and by_id['c']['ai_warning'] is None)
check('la explicación viaja en la fila', by_id['a']['why'].startswith('es director'))
check('fortalezas y riesgos viajan en la fila',
      by_id['a']['ai_risks'] == ['sin cuota comercial'] and by_id['b']['ai_strengths'][0]['quote'] == 'cuota')

# Acciones relativas sobre la puntuación final: top 5 Entrevistar, siguientes 10 Backup, mínimo 55
many = [row(f'c{i}', 90 - i) for i in range(20)]
rows = AIRefineService.unify(many, [], set(), None, True)
actions = [r['action'] for r in rows]
check('top 5 entrevistar', actions[:5] == ['interview'] * 5, str(actions[:6]))
check('siguientes 10 backup', actions[5:15] == ['backup'] * 10)
check('el resto prioridad baja', set(actions[15:]) == {'low_priority'})
check('mínimo 55 respetado',
      all(r['action'] in ('low_priority', 'do_not_advance_knockout') for r in rows if r['final_score'] < 55))

# Un fit bajo puede bajar a alguien de Entrevistar sin crear otro ranking
mixed = [row('top', 58), row('solid', 56)]
fits2 = {'top': {'fit': 10, 'why': 'no hay evidencia comercial', 'evidence_verified': False, 'strengths': [], 'risks': []},
         'solid': {'fit': 85, 'why': 'director comercial en telecom', 'evidence_verified': True, 'strengths': [], 'risks': []}}
rows = AIRefineService.unify(mixed, [], set(), fits2, True)
check('un fit bajo mueve al candidato dentro de la MISMA lista',
      rows[0]['candidate_id'] == 'solid' and rows[1]['candidate_id'] == 'top',
      str([(r['candidate_id'], r['final_score'], r['action']) for r in rows]))

# Bono por criterios de "Afinar con IA": cumple +6, parcial +3, tope +12
crit = [{'id': 'c1', 'text': 'Telecom', 'kind': 'criterion', 'status': 'done',
         'results': {'a': {'status': 'cumple'}, 'b': {'status': 'parcial'}, 'c': {'status': 'no_cumple'}}},
        {'id': 'c2', 'text': 'Cuota comercial', 'kind': 'criterion', 'status': 'done',
         'results': {'a': {'status': 'cumple'}, 'b': {'status': 'cumple'}, 'c': {'status': 'no_cumple'}}},
        {'id': 'c3', 'text': 'Inglés', 'kind': 'criterion', 'status': 'done',
         'results': {'a': {'status': 'cumple'}, 'b': {'status': 'cumple'}, 'c': {'status': 'parcial'}}}]
rows = AIRefineService.unify([row('a', 60), row('b', 60), row('c', 60)], crit, set(), None, True)
by_id = {r['candidate_id']: r for r in rows}
check('tope del bono en +12', by_id['a']['criteria_bonus'] == 12, str(by_id['a']['criteria_bonus']))
check('bono mixto 6+6+3 = 12 (tope)', by_id['b']['criteria_bonus'] == 12, str(by_id['b']['criteria_bonus']))
check('parcial suma 3', by_id['c']['criteria_bonus'] == 3, str(by_id['c']['criteria_bonus']))
check('el bono entra en la puntuación final', by_id['a']['final_score'] == 72 and by_id['c']['final_score'] == 63,
      f"{by_id['a']['final_score']}/{by_id['c']['final_score']}")
check('cumple todos los criterios solo si están los 3 en cumple',
      by_id['a']['criteria_all_met'] and not by_id['b']['criteria_all_met'] and not by_id['c']['criteria_all_met'])
check('base sin bono se conserva aparte', by_id['a']['base_score'] == 60)
check('sin motor único no hay bono', AIRefineService.unify([row('a', 60)], crit, set(), None, False)[0]['criteria_bonus'] == 0)
check('final nunca pasa de 100', AIRefineService.unify([row('a', 97)], crit, set(), None, True)[0]['final_score'] == 100)

if __name__ == '__main__':

    print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
    sys.exit(0 if all(ok for _, ok in results) else 1)
