"""Duplicados probables: regla, pares y colapso en el ranking (sin fusionar)."""
import sys
from datetime import date

sys.path.insert(0, '/app/backend')
from probable_duplicates import collapse_duplicates, duplicate_reason, find_duplicate_pairs, shared_employers  # noqa: E402

TODAY = date(2026, 10, 13)
results = []


def check(name, ok, extra=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{extra}]' if extra else ''))


esp = {'id': '1', 'full_name': 'Luis Lopez Cruz', 'email': 'lm@x.com', 'phone': '+52 55 1234 5678',
       'previous_companies': [
           {'company_name': 'GLC/Megacable', 'start_date': '2025-01', 'end_date': None},
           {'company_name': 'Grupo Salinas', 'start_date': '2022-01', 'end_date': '2025-01'},
           {'company_name': 'BJX Telecom', 'start_date': '2018-01', 'end_date': '2021-01'},
           {'company_name': 'Telefónica Movistar', 'start_date': '2012-01', 'end_date': '2018-01'}]}
eng = {'id': '2', 'full_name': 'Luis López', 'email': 'otro@x.com', 'phone': '555 000 1111',
       'previous_companies': [
           {'company_name': 'Megacable', 'start_date': '2025-01', 'end_date': None},
           {'company_name': 'Grupo Salinas S.A. de C.V.', 'start_date': '2022-03', 'end_date': '2025-02'},
           {'company_name': 'BJX Telecom Mexico', 'start_date': '2018-02', 'end_date': '2021-03'},
           {'company_name': 'Movistar', 'start_date': '2012-02', 'end_date': '2018-02'}]}

check('empleadores coincidentes detectados', len(shared_employers(esp, eng, TODAY)) >= 2,
      str(shared_employers(esp, eng, TODAY)))
reason = duplicate_reason(esp, eng, TODAY)
check('Luis Lopez Cruz ↔ Luis López es duplicado probable', bool(reason), str(reason))

check('mismo email basta', bool(duplicate_reason({'full_name': 'Ana Pérez', 'email': 'a@x.com'},
                                                 {'full_name': 'Otra Persona', 'email': 'a@x.com'}, TODAY)))
check('mismo teléfono basta', bool(duplicate_reason({'full_name': 'Ana Pérez', 'phone': '+52 (55) 1234-5678'},
                                                    {'full_name': 'Otra Persona', 'phone': '5512345678'}, TODAY)))
check('nombre parecido sin empleadores en común no es duplicado',
      duplicate_reason({'full_name': 'Luis López', 'previous_companies': [{'company_name': 'Acme', 'start_date': '2020-01'}]},
                       {'full_name': 'Luis López Cruz', 'previous_companies': [{'company_name': 'Zeta', 'start_date': '2020-01'}]},
                       TODAY) is None)
check('un solo empleador en común no alcanza',
      duplicate_reason({'full_name': 'Luis López', 'previous_companies': [{'company_name': 'Acme', 'start_date': '2020-01'}]},
                       {'full_name': 'Luis López Cruz', 'previous_companies': [{'company_name': 'Acme', 'start_date': '2020-01'}]},
                       TODAY) is None)
check('personas distintas no se marcan',
      duplicate_reason({'full_name': 'Ana Gómez', 'email': 'a@x.com'},
                       {'full_name': 'Beto Ruiz', 'email': 'b@x.com'}, TODAY) is None)
check('mismos empleadores sin fechas traslapadas no cuenta',
      duplicate_reason({'full_name': 'Luis López', 'previous_companies': [
          {'company_name': 'Acme', 'start_date': '2000-01', 'end_date': '2002-01'},
          {'company_name': 'Zeta', 'start_date': '2002-01', 'end_date': '2004-01'}]},
          {'full_name': 'Luis López Cruz', 'previous_companies': [
              {'company_name': 'Acme', 'start_date': '2020-01', 'end_date': '2022-01'},
              {'company_name': 'Zeta', 'start_date': '2022-01', 'end_date': '2024-01'}]}, TODAY) is None)

pairs = find_duplicate_pairs([esp, eng, {'id': '3', 'full_name': 'Otro Candidato'}], TODAY)
check('find_duplicate_pairs devuelve un par con motivo', len(pairs) == 1 and 'motivo' in pairs[0], str(pairs))

# Colapso en el ranking: solo queda el de mejor puntuación, con el aviso
rows = [{'candidate_id': '1', 'candidate_name': 'Luis Lopez Cruz', 'final_score': 66},
        {'candidate_id': '9', 'candidate_name': 'Alguien más', 'final_score': 64},
        {'candidate_id': '2', 'candidate_name': 'Luis López', 'final_score': 63}]
kept = collapse_duplicates(rows, {'1': esp, '2': eng}, today=TODAY)
check('el ranking deja una sola fila del par', len(kept) == 2 and [r['candidate_id'] for r in kept] == ['1', '9'],
      str([r['candidate_id'] for r in kept]))
check('la fila que queda trae el aviso con el nombre del otro',
      kept[0].get('duplicate_of', {}).get('nombre') == 'Luis López', str(kept[0].get('duplicate_of')))
check('la fila del otro candidato no se toca', 'duplicate_of' not in kept[1])

# Si el duplicado tiene mejor puntuación, se queda el mejor
rows_inv = [{'candidate_id': '2', 'candidate_name': 'Luis López', 'final_score': 70},
            {'candidate_id': '1', 'candidate_name': 'Luis Lopez Cruz', 'final_score': 60}]
kept_inv = collapse_duplicates(rows_inv, {'1': esp, '2': eng}, today=TODAY)
check('se conserva el de mejor puntuación', len(kept_inv) == 1 and kept_inv[0]['candidate_id'] == '2',
      str([r['candidate_id'] for r in kept_inv]))

if __name__ == '__main__':

    print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
    sys.exit(0 if all(ok for _, ok in results) else 1)
