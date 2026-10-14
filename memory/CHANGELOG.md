# CHANGELOG - Humaniq Talent Vault

## 2026-10-14 (segunda parte) — Limpieza histórica de empleos repetidos, pruebas aisladas y refuerzo de `fill_missing_from_extras`
- **Pruebas que escriben en la base compartida desactivadas por defecto**: `tests/test_identical_cv_flow.py` y `tests/test_duplicates_trash_jobs_cycle.py` ahora hacen `SKIP` salvo `ALLOW_LIVE_DB_TESTS=1`.
- **Inventario de fichas sintéticas (solo lectura)**: 92 fichas de prueba en Atlas (`TEST_Carga Paralela`, `Ana/Bruno/Carla/Daniel BatchXXXX`, `ZZTest`), **todas con borrado lógico** (0 activas), creadas entre el 2026-07-07 y el 2026-09-22; 1 vacante con nombre de prueba; 0 usuarios de prueba. Nada se borró. Lista en `test_reports/synthetic_and_education_report.json`.
- **`fill_missing_from_extras` reforzado**: `education` y `certifications` entran a `NO_APPEND_LIST_FIELDS` (no se concatenan, solo se copian si la ficha conservada está vacía); `skills`, `languages` y `tags` se unen sin repetir ignorando mayúsculas y acentos (`_text_key`). Dato: hoy ninguna ficha tiene educación ni certificaciones capturadas (0 de 687), así que no hay repetidos históricos que limpiar. Prueba `test_fill_missing_no_append.py` 9/9.
- **Limpieza histórica aplicada** (`scripts/cleanup_duplicate_experience.py --apply`): **128 fichas tocadas, 831 empleos repetidos eliminados** (esperado 843, dentro del ±5%). 3 fichas se restauraron con la foto previa de `cv_versions` (Allan David Méndez 18→6, Ricardo Cruz 10→5, Gamaliel González 21→7) y 125 se colapsaron con la regla estricta (mismo empleador + inicio y fin ±2 meses, conservando la descripción más larga y anotando "También listado como: …"). Los años de experiencia NO se tocaron (solo se reportó el recálculo de referencia). Respaldo: `previous_companies_pre_dedupe` + colección `experience_cleanup_backups` + `/app/memory/backups/experience_cleanup_20261014_175138.json`. Verificación posterior: quedan 7 fichas con 12 empleos repetidos, las de revisión manual.
- **7 fichas para revisión manual** (sin evidencia de limpieza de CV idéntico, no se tocaron): Luis Fernando Rojas Torres, Juan José Hernández, Alejandro Arellano Flores, Ana Lucia Treviño Gómez, Angel Gutierrez, Anel Lizbeth Díaz Prado, Daniela Alejandra Aguilar Aguilar.
- **`experience_dedupe.collapse_strict_duplicates()`** nuevo: colapsa solo duplicados estrictos, conserva la posición original del historial, la descripción más larga y los títulos distintos. 35/35 pruebas.
- **Bug "Chrome ha bloqueado esta página"**: segunda ronda de pruebas sin reproducción. El botón "Perfil" de la tarjeta de terna (Reyes, 3.º) funciona en pestaña propia y dentro de un iframe que simula el panel de vista previa (localStorage accesible dentro del iframe, token leído correcto). `openCandidate` usa `navigate()` de React Router: no hay `target="_blank"` ni `window.open` en ese flujo; el único `window.open` es "abrir ficha del duplicado" en `CandidateDetailPage.js:612`, que dentro de un iframe sí puede caer en el bloqueador de pop-ups. Logs del backend: cero respuestas 429 en todo el histórico y ningún registro entre las 17:00 y 17:30 UTC de hoy (el proceso reinició a las 17:47); los 401 del log son llamadas sin token de scripts de prueba.


## 2026-10-14 — Scripts de escritura fuera de tests, causa raíz de empleos repetidos y re-parseo de fichas vacías
- **Scripts movidos** de `backend/tests/` a `backend/scripts/`: `dedupe_merged_experience.py`, `fix_experience_years.py`, `report_strict_duplicates.py`, `dryrun_reparse_empty.py`, `diag_pendientes.py`, `scan_probable_duplicates.py`. Todos simulan por defecto y solo escriben con `--apply`; ahora corren bajo `if __name__ == '__main__'` (importarlos no ejecuta nada) y pytest no los recoge (no empiezan con `test_`, colección vacía verificada).
- **CAUSA RAÍZ de los 843 empleos repetidos en 135 fichas**: `CVHashService.fill_missing_from_extras` (llamado desde `POST /api/duplicates/identical-cv/delete-extras`, server.py:3589) concatenaba `previous_companies` de las fichas sobrantes comparando diccionarios con igualdad exacta; como cada ficha se parseó en momentos distintos, el mismo empleo volvía con otro formato de fecha o de nombre y se agregaba. Evidencia: Allan David Méndez Castillo pasó de 6 a 18 empleos el 2026-09-29 22:55:40, exactamente las historias de sus 2 fichas borradas (`duplicate_of`); Humberto/otros muestran pares como "Programador @ Hypercomm México (07/2006 → 12/2006)" y "(2006-07 → 2006-12)". Atribución: 128 de 135 fichas pasaron por esa limpieza (151 ejecuciones entre el 29-sep y el 9-oct), 1 traía el duplicado desde el parseo original y 6 sin evidencia. **Corregido**: el historial laboral ya no se concatena, solo se copia si la ficha conservada no tiene ninguno (`NO_APPEND_LIST_FIELDS`). Prueba nueva `tests/test_fill_missing_no_append.py` 6/6 con Mongo falso en memoria. Los datos históricos NO se tocaron.
- **12 fichas sin empleos o sin años re-parseadas** con `scripts/reparse_empty_candidates.py --apply`: respaldo completo en `/app/memory/backups/reparse_empty_20261014_165646.json` + colección `reparse_backups`. Solo se rellenó lo vacío; nunca se sobrescribió un valor existente (Antonio Alegria conservó sus 20 años aunque el CV sugería 15) ni la clasificación. Resultado: 11 fichas pasaron de 0 empleos a 1-9, y 10 recuperaron años (6 a 25). Ninguna quedó con empleos repetidos. Tabla en `test_reports/reparse_empty_candidates.json`.
- **Bug "Chrome ha bloqueado esta página"**: no reproducible. El perfil de José Luis Reyes Arroyo abre bien, igual que los CV en PDF (Reyes, Ochoa) y en DOCX (De la Vega); las respuestas no traen `Content-Security-Policy`, `X-Frame-Options` ni cabeceras `Cross-Origin-*`; los únicos usos de `blob:` son el `<iframe>` del visor y el ancla de descarga (permitidos por Chrome); el CV de Reyes baja correcto (PDF, 131 KB). Pendiente el código de error exacto del usuario.
- Reportes nuevos: `test_reports/root_cause_duplicates.json`, `test_reports/reparse_empty_candidates.json`.


## 2026-10-13 — Chips informativos, PDF del shortlist, flag por defecto y pendientes de datos
Checkpoint previo: tag git `checkpoint-20261013_181452` (commit 75e76b8) + `/root/backups/checkpoint_20261013_181452/app_code.tgz`. **No desplegado.**

**A/C/D — Chips (`frontend/src/components/CandidateNotices.js`, reescrito)**
- En la línea del nombre, antes de la puntuación. Máximo 2 visibles + "+N" con tooltip. Prioridad: Duplicado > Inestable > Revisar > Edad.
- Textos con el dato dentro: "Inestable · 4 en 5a" (coral `#FF6B5B`, texto `#272727` por contraste), "Revisar · 3 en 5a" (`#FFAA00` / `#272727`), "≈50+ · est. 48–54" (sin relleno, borde/texto `#0092AE`), "Posible duplicado" (sin relleno, borde/texto `#272727`, enlaza a /duplicates).
- Space Grotesk 11.5 px (fuente agregada en `frontend/public/index.html`), radio 4 px, sin sombras ni degradados. Tooltip con timeline/fuente de edad/motivo del duplicado; abre con hover y con foco (toque en móvil). La alerta ⚠ (HMS − fit ≥ 25) quedó intacta y separada.
- Ficha: los chips se movieron a la línea del título (`CandidateDetailPage.js`).

**B — PDF del shortlist (`backend/templates/shortlist_report.html` reescrito, `export_service.py`)**
- Paleta: fondo blanco, títulos `#272727`, acentos/líneas `#0092AE`, chips de competencias con borde `#77C5D5`. Sin azul marino ni degradados.
- Poppins (nombres/títulos) y Space Grotesk (fechas, empresas, etiquetas) **incrustadas desde disco** (`backend/assets/fonts/*.ttf`, `base_url` local; variable de Space Grotesk instanciada a 400/500/700). Cero llamadas a Google Fonts.
- Portada con logo `backend/assets/humaniq-logo.png`, vacante, cliente, fecha en español, preparado por y "Perfil buscado" en viñetas reales (`summary_bullets`).
- Encabezado de candidato: nombre + puesto @ empresa + industria (`industry_label` vía `get_industry_display_name`). Se eliminó el recuadro HMS/acción.
- `clean_markdown` ahora quita el encabezado "Nombre - Resumen Profesional Ejecutivo" pegado al resumen; `title_case_if_shouting` conserva siglas (`R3D BR1DG3`, `AT&T`) y solo minusculiza conectores.
- Bug corregido: `export_custom_candidates` pasaba `include_scores` sin definir (la exportación de selección custom en PDF tronaba).

**Flag del motor único**
- `single_ranking_active()`: **encendido por defecto** en todos los ambientes. Se apaga solo con `false` explícito, en `app_settings.single_ranking` (gana si existe) o con `SINGLE_RANKING=false` en el `.env` del ambiente. Nota en el código: `app_settings` es la MISMA base para preview y producción; no usarlo para pruebas.
- Pantalla y export usan el mismo ranking con el flag en cualquier estado: `POST /api/exports/job/{id}` ya no lee el snapshot, recalcula con `build_unified_matches` (solo caché, sin llamadas nuevas de IA) y lo pasa como `ranking_rows`.

**Datos (con aprobación explícita del usuario)**
- `experience_dedupe.py`: agrupamiento **transitivo** (independiente del orden) y preservación de trayectoria al colapsar: título = puesto más reciente + "Roles: X 2005–2010; …" en la descripción + `merged_roles`. Nuevo `strict_duplicates()` (±2 meses) y `experience_years_from_history()` (lapso del primer empleo sin prácticas al último menos huecos de 12+ meses).
- Dedupe aplicado SOLO a fichas fusionadas: 1 ficha pendiente, **Humberto David Hernández Pérez 8 → 4 empleos** (Coca-Cola FEMSA colapsado con los 5 roles listados, años 19 sin cambio). Respaldo `/app/memory/backups/experience_dedupe_20261013_185209.json` + colección `experience_dedupe_backups`.
- Años de experiencia de las 10 fichas que habían bajado: con la regla del usuario los valores actuales resultaron correctos; solo subieron 3 (Cesia González 9→10, Gabriela Martínez 14→15, Berenice Gómora 9→10). Previo guardado en `years_experience_pre_fix` (no se tocó `years_experience_pre_dedupe`). El resto de la base NO se recalculó: 276 de 659 fichas cambiarían más de 2 años con esa regla.
- Reportes solo lectura: `test_reports/strict_duplicates_report.json` (135 fichas no fusionadas, 843 empleos repetidos con la regla estricta), `test_reports/dryrun_reparse_empty.json` (12 fichas sin empleos/sin años: todas legibles, el re-parseo llenaría empleos y años), `test_reports/pendientes_diagnostico.json`, `test_reports/fix_experience_years.json`.
- OCR "CV Ismael Hdz 2027.pdf": funciona (0 caracteres nativos, 4,938 por OCR, `readable: true`, ficha completa con confianza 88%). No se tocó el parser.

**Pruebas:** `test_experience_dedupe.py` 29/29 (incluye "puestos secuenciales con fechas de solo año NUNCA colapsan", caso Movistar) · `test_flag_pdf_format.py` 15/15 (nuevo: flag por defecto, viñetas, fuentes incrustadas, sin HMS en el PDF) · `test_stability_alert.py` 22/22 · `test_age_estimate.py` 12/12 · `test_probable_duplicates.py` 13/13 · `test_single_ranking_unify.py` 27/27 · `test_export_shortlist.py` 12/12. UI verificada en preview (chips, tooltip, ranking intacto) y PDF real de "Director Comercial" revisado página por página.


## 2026-10-12 (segunda parte) — Motor único prendido en preview, bono por criterios y limpieza de duplicados
- **Flag `single_ranking` ACTIVADO** (`PUT /api/settings/single-ranking?active=true`) para revisión del usuario en preview. Ojo: el documento vive en la misma base Atlas que producción; el código desplegado del 30-sep lo ignora, pero quedará activo en cuanto se despliegue esta versión.
- **Bono por criterios de "Afinar con IA"**: cumple +6, parcial +3, tope +12 por candidato, sumado a la puntuación final (`criteria_bonus`, `base_score`, `criteria_all_met` en cada fila). Solo aplica con el motor único activo.
- **Criterios extendidos al top del ranking**: `AIRefineService.extend_to_top()` evalúa los criterios ya existentes en los candidatos que ENTRAN al top 30 al actualizar, para que todos compitan en igualdad (se llama desde `POST /jobs/{id}/ranking/refresh`).
- **Filtro "Solo los que cumplen todos los criterios"** en la lista (cuenta "X de Y candidatos"); los no-negociables no cuentan para ese filtro porque ya ajustan K.
- **Años por UNIÓN de periodos** (`industry_trajectory`): `merge_periods`, `union_years`, `weighted_union_years`, `employment_periods`, `total_experience_years`. `industry_affinity` ahora calcula `total_w`, `known_w`, `target_w` y `target_years` sobre la unión: **dos empleos simultáneos ya no cuentan doble** (antes sí). Los pesos de `config_v3.py` no se tocaron.
- **Limpieza de duplicados de experiencia aplicada a 33 fichas fusionadas** (31 + 2 en la segunda pasada) con `tests/dedupe_merged_experience.py --apply`: respaldo en `/app/memory/backups/experience_dedupe_*.json` + colección `experience_dedupe_backups`, original en `previous_companies_pre_dedupe` y `years_experience_pre_dedupe`, años recalculados por unión de periodos. Matthias Tiedemann Becker 15 → 8 empleos (4 periodos de Siemens conservados), años 25 → 29. `_month` ahora usa `parse_date` para comparar fechas tipo "oct 2014". Queda **1 ficha sin tocar** (Humberto David Hernández Pérez): tiene un registro paraguas de Coca-Cola FEMSA 2005-2019 que traslapa los ascensos internos; fusionarlo borraría la escalera de puestos.
- **Pruebas:** `tests/test_single_ranking_unify.py` 27/27 (incluye bono, tope e igualdad de criterios) · `tests/test_period_union.py` 12/12 · `tests/test_experience_dedupe.py` 14/14 · `scoring/tests/test_industry_trajectory.py` 8/8 · refresh real de las dos vacantes y UI verificada con Playwright (15 filas, terna, filtro 1 de 50, "HMS 73 · fit IA 92 · criterios +12").
- **Pendiente de decisión:** 6 fichas donde los años recalculados bajan más de 3 años porque el CV tiene empleos sin fechas (Mario Gutiérrez 23→17, Martín Buendía 15→7, David Montiel 10→5, Berenice Gómora 14→9, Cesia González 13→9, Jose Abel Espinosa 15→12); se puede restaurar el valor declarado desde `years_experience_pre_dedupe`.


## 2026-10-12 — Motor único de matching (construido, pendiente de activación) + industria manual
**Diagnóstico:** en la página de vacante había dos rankings. (1) `MatchV3Results` = lista unificada (HMS v3 + criterios de "Afinar con IA" + no-negociables), ordenada por tier de knockouts → criterios cumplidos → HMS, lo que subía a Fernando Vázquez (HMS 56) por encima de Edgar Ochoa (HMS 73). (2) `AIMatchReview` = tarjeta aparte de terna IA (Opus 5.5) que recibía el scorecard pero con un prompt de "criterio profesional propio" y SIN el texto completo del CV (solo `ai_summary` ≤700 caracteres), y devolvía una categoría fit alto/medio/bajo fuera del orden: marcó "fit bajo" a los 5 primeros. v2 ya no se mostraba en la página (solo backend bajo `MATCHING_ENGINE_VERSION`).

**Construido (motor único por capas):**
- `ai_fit_service.py` (capa 3): lee el CV completo del top 30 por HMS y califica 0-100 **solo** con los criterios del scorecard (industrias objetivo + requisito, skills, no negociables, seniority, process_type, calibre, idiomas, ubicación). Citas verificadas literalmente contra el texto; sin una sola cita verificable el fit se topa en 50. Caché por (candidato, versión de CV, versión del scorecard) en `ai_fit_evaluations`; costo estimado por corrida. Modelo configurable: nueva tarea `fit_scoring` (default `claude-sonnet-5-5`).
- Puntuación final = **0.75·HMS + 0.25·fit IA** (`final_score`); sin fit evaluado la final es el HMS. Calidad y acciones relativas (top 5 Entrevistar, siguientes 10 Backup, mínimo 55) se calculan sobre la final. Alerta en la misma fila cuando HMS − fit ≥ 25: "⚠ La lectura del CV no confirma: …". Nunca hay un segundo veredicto.
- `AIRefineService.unify(..., fits, single)`: con `single=True` ordena por (fatal al final → puntuación final → criterios IA como desempate → orden v3). Con `single=False` conserva exactamente el orden anterior, así el flag apagado no cambia nada.
- Endpoints: `GET /api/jobs/{id}/ranking` (lee lo guardado, sin gastar IA), `POST /api/jobs/{id}/ranking/refresh` (corre knockouts → HMS v3 → fit IA y guarda UN solo snapshot `unified`), `GET|PUT /api/settings/single-ranking` (flag de activación, PUT solo admin).
- Frontend: un solo bloque "Ranking de candidatos" con los 15 mejores, terna = top 3 resaltados, línea "Por qué está aquí", sub-línea "HMS x · fit IA y", alerta de discrepancia, desglose con fortalezas/riesgos citados (todos los roles) y componentes (solo admin), botón único "Actualizar ranking". `AIMatchReview` se oculta cuando el flag está activo.
- **Flag apagado por defecto**: la vista por defecto sigue siendo la anterior hasta que el usuario dé el OK.

**Otros cambios:** `experience_dedupe.py` (empresa normalizada similar + periodos traslapados, conserva el registro más completo) integrado en el fusionador (`duplicate_detector_v2`); `PATCH /api/candidates/{id}/previous-companies/{index}/industry` + selector manual del catálogo en la ficha con etiqueta "Industria sin detectar" (sin botón de IA, por decisión del usuario). El cruce de carpeta en la app NO se construyó (el usuario lo descartó).

**Pruebas:** `tests/test_single_ranking_unify.py` 19/19 · `tests/test_experience_dedupe.py` 14/14 · `tests/test_clean_previous_company_types.py` 13/13 · `tests/test_e2e_batch_upload.py` 9/9 (3 CVs reales + segundo lote + recarga) · curls de los endpoints nuevos (400/404 de validación incluidos) · UI verificada con Playwright (ranking único con terna y desglose; selector de industria guardando y persistiendo). Simulación: `tests/simulate_single_ranking.py` (antes/después de Director Comercial y Director de Finanzas, costo real $0.86 la primera corrida, luego $0 por caché).

**Pendiente de decisión del usuario:** activar el flag; limpiar duplicados de experiencia en Matthias Tiedemann Becker (15 → 8) y en las 31 de 46 fichas fusionadas afectadas; definir si los criterios de "Afinar con IA" deben pesar más que como desempate.


## 2026-10-09 — `company_industry` con tipos inesperados ya no tumba al candidato
- `clean_previous_company` (server.py): `company_industry` se valida con `isinstance(..., str)` antes de comparar contra `INDUSTRY_KEYS`. Lista, dict, número o valor fuera del catálogo → `None`. Antes, una lista provocaba `TypeError: unhashable type: 'list'` y descartaba el candidato completo.
- `clean_previous_companies`: cada empleo va en `try/except`; un empleo malformado se registra en log y se salta sin afectar al resto.
- Prueba: `backend/tests/test_clean_previous_company_types.py` 13/13 (incluye `["telecom"]`, dict, número, valor fuera de catálogo, `company_caliber` como lista y lista mixta).
- Herramienta nueva de lectura: `backend/tests/cross_check_cv_hashes.py` cruza un CSV (archivo + sha256) contra `cv_hashes` activos en Atlas y, para los que no coinciden por hash, busca por nombre normalizado del archivo. Validada con 5 filas reales.
- Cruce ejecutado con `cvs_director_comercial_sha256.csv` (57 CVs, carpeta Director Comercial): **48 ya están por hash exacto**; **1 ya está con otra versión del archivo** (`Resume Alejandro Cancino 2026 Fs.docx`: mismo nombre de archivo y mismo candidato `6153ef42-d82a-4a97-87db-dd7c913f183d`, sha256 distinto); **8 no están** (Juan Gregg, Paulina Molo Esteban, Raúl Ducoing, Ramón Alberto Ponce Campos, Guillermo Marcelo Sánchez Montemayor, Martín Buendía —dos archivos ES/EN— y Sergio Moba), verificado por sha256 en todo `cv_hashes` (activos e inactivos) y por apellido distintivo en los 665 candidatos vigentes más los eliminados. Solo lectura, sin mutaciones.


## 2026-10-09 — Carga de lotes: diagnóstico y blindaje (urgente)
**Diagnóstico (hechos verificados):**
- Ambiente del usuario: **producción** `https://atlas-recruiting-ai.emergent.host`, imagen desplegada 2026-09-30, que **sí** incluye el código de cuota de lotes. Producción y preview apuntan a la **misma base Atlas** (`ATLAS_URI`, `ATLAS_DB_NAME=atlas_talent_vault`). La base gestionada por Emergent (`atlas-recruiting-ai-atlas_talent_vault`) está sin usar (solo `smart_folders`) y por eso DB Manager/mongo_query no ven datos reales. Producción corre con **2 réplicas**.
- Reproducción con la cuenta del dueño en producción: `POST /api/candidates/upload-batch` → 200; `GET /api/candidates/batch/{id}` → 200 hasta `is_complete`. **No se reprodujo 403/404 desde la API.**
- Atlas: sin lotes del dueño ese día (último real 2026-07-07) y `ai_user_workloads` vacío → no había leases vivos bloqueando. Sí había **7 lotes huérfanos** de julio con jobs `pending/processing` eternos (bytes perdidos en réplicas muertas), que el heartbeat mantenía "frescos" y podían ocupar cuota e impedir que un lote completara.
- El mensaje exacto "Este lote no está disponible" solo se produce con un `batch_id` en `localStorage` que ya no existe en la base (GET 404). Reproducido en navegador y corregido.

**Correcciones aplicadas:**
- `ai_workload_limits.py`: `reserve_batch` barre y libera lotes sin trabajo pendiente antes de devolver 429 (`release_idle_batches`, gracia de 120 s con `reserved_at`); el heartbeat solo refresca jobs cuyos bytes siguen en memoria de esa réplica, para que la detección de huérfanos funcione.
- `background_processor.py`: job sin bytes en memoria se marca `failed` (`_mark_orphan_job`) en vez de quedar `pending` eterno; `get_batch_status` libera siempre la cuota de lotes terminados/huérfanos; `sweep_orphan_batches()` al arranque cierra lotes de réplicas muertas (limpió los 7 de julio: 0 jobs colgados).
- `UploadBatchContext.js`: 404 → limpia el seguimiento solo, avisa y deja subir de nuevo (nunca bloquea); 429 → "Tienes un lote en proceso; espera a que termine" y pasa a seguir el lote real; 401 → "Tu sesión expiró"; 403 → mensaje de permisos.
- Actualización de CV (punto 5): confirmado que `previous_companies` solo se reemplaza si el CV nuevo trae ≥1 empleo parseado; cubierto ahora con prueba E2E.

**Pruebas:** `tests/test_batch_quota_selfheal.py` 6/6 (Mongo local aislado); `tests/test_e2e_batch_upload.py` 9/9 en preview (lote de 3, segundo lote inmediato, consulta a media carga, 404 de lote inexistente, tercer lote sin 429); `tests/test_cv_update_keeps_history.py` PASS (trayectoria intacta con CV sin empleos); UI con Playwright: carga de 3 CVs + recarga a media carga → progreso recuperado, 3 exitosos, sin banner de error; CVs sintéticos de prueba eliminados de Atlas.

**Observación (no corregida, fuera de alcance):** en un CV sintético el parser dejó `company_industry: null` para una empresa cuya industria estaba descrita en el texto ("manufactura de componentes automotrices"); es una omisión del modelo, no de la validación de catálogo.


## 2026-09-22 — CAPA 1 y CAPA 2 completadas en orden
- Capa 1: DOCX tablas/cuadros/encabezados/pies, alternativa PDF y OCR por página (Poppler+Tesseract spa/eng instalados y preparación idempotente). 12 tests pasan tras corregir AlternateContent.
- Reprocesados solo 34 IDs autorizados con clasificador original. **34 legibles, 34 autoclasificados con cuatro campos completos, 0 ilegibles y 0 pendientes**, confianzas 78%-95%. Sin aprobaciones humanas. Before-images en cv_reprocessing_runs e historial/archivos preservados.
- Resultado de Capa 1 entregado antes de comenzar Capa 2.
- Capa 2: wrapper condicional <75%/faltantes/no canónicos, prompt CV completo, industria por meses de última década, años con periodos unidos, seniority por responsabilidad; JSON/evidencia validados. Modelo/SDK originales preservados.
- Caché por CV/proceso y empresas, deduplicación concurrente, sin web. Estados de captura manual y avisos visibles; botones individuales/masivos activos con jobs persistidos y progreso recuperable.
- No se llamó a segunda pasada para los 34 ya resueltos. Una llamada real con CV sintético verificó modelo/cache; pruebas de UI MOCKED solo para proteger Atlas. 47 regresiones finales pasan; build y responsive correctos.
- Scoring/, job_matching_service.py, pesos, hybrid_search_service.py y atlas_service.py con diff vacío contra35947513ee5c0cd6ab7fa7b96967919538e170e3.
- Hallazgos globales antiguos fuera de alcance permanecen congelados; sin nuevas credenciales ni cambios de claves.

## 2026-09-22 — Diagnóstico de CVs, bandeja de revisión y continuidad de carga
- Diagnóstico read-only de 34 registros reportado antes de cambios: omisiones de tablas/cuadros DOCX, OCR fallido por Poppler, PDFs mixtos, claves no canónicas y casos de clasificación nula con texto. Informe nominal privado en `/root/humaniq_cv_diagnosis/report.md`.
- Selección global de pendientes, aprobación en lote, cuatro dropdowns con guardado inmediato sin autoaprobar ni elevar confianza. Validación de catálogo y protección contra aprobar fichas vacías.
- Segunda pasada SOLO propuesta; controles deshabilitados esperando aprobación. Clasificador y parser sin cambios.
- Proveedor de seguimiento de lotes entre rutas, referencia local por usuario y recuperación del backend; resincronización por foco/visibilidad/conexión. Recepción/finalización y archivos rechazados persistidos.
- Responsive de revisión/carga corregido y menú lateral adaptado a móvil.
- Testing: 19 backend aislados, pruebas UI con mutaciones MOCKED solo para proteger producción, selección real de 34 y 8 validaciones responsive. Test incompatible migrado a AnyIO sin cambiar dependencias de aplicación.
- Documentos originales de los 34 candidatos sin cambios. Diff de scoring/pesos/matching vacío contra baseline `4b06061333ac105ad5704ca4baa92c217993000d`. Sin integración IA adicional ni costos de reclasificación.

## 2026-09-22 — Baja de Patricia Sáez
- Cuenta `psaez@humaniq.com.mx` (`bb8ac7a2-ba5b-4312-9baa-f2bbf973f4bc`) desactivada mediante la API existente: `is_active: false`, HTTP 200; cuenta conservada y excluida de usuarios activos.
- Sin cambios en código, contraseña, candidatos, notas o asignaciones. En el documento de usuario expuesto por API solo cambiaron `is_active` y `updated_at`.
- Verificado HTTP 403 `Cuenta desactivada` en `/api/auth/me` con JWT de comprobación válido, efímero y no persistido.
- Login con contraseña desconocida/aleatoria: HTTP 401. Login con contraseña correcta NO probado porque no está disponible; la implementación verifica contraseña antes de devolver 403 por estado inactivo. No afirmar que se verificó 403 en `/api/auth/login`.
- Comparación literal de candidatos no concluyente por valores `classified_at` generados por el modelo en cada respuesta; diferencia reproducida con GET consecutivos, sin modificar datos.
- PRD dividido para mantenerlo conciso; historial anterior completo en `CHANGELOG_LEGACY.md`, pendientes en `ROADMAP.md`.

## 2026-07-16 — Limpieza de cuentas Atlas + hardening `is_active`

### Cuentas
- Desactivadas 6 cuentas de prueba (`is_active: False`, historial preservado):
  test_user_011349, test_user_011402, test_user_b3fc4cd1, test_user_a7068b0c,
  test_user_fa5b2128, recruiter_test @atlas.com
- Desactivadas 4 cuentas viejas @atlas.com reemplazadas por invitaciones a
  humaniq.com.mx / hqts.com.mx: patricia, ximena, alejandra, viridiana
- Rotada la contraseña de `test_utf8@atlas.com`; guardada únicamente en
  `/app/memory/test_credentials.md` (password anterior invalidada).
- `test_utf8` marcado explícitamente `is_active: True`.

### Seguridad (fix crítico)
- `POST /api/auth/login`: ahora responde **403 "Cuenta desactivada"** cuando
  `is_active === False` (antes emitía JWT válido).
- `get_current_user`: mismo bloqueo → tokens vivos de usuarios desactivados
  quedan invalidados en la siguiente request.
- Verificado con curl real: patricia@atlas.com → 403; test_utf8 (nueva pwd) → 200; dtejedo → 200.

### Scripts (nuevos, en `/app/backend/scripts/`)
- `list_all_users.py` — dump con rol/is_active/last_login
- `deactivate_and_rotate.py` — desactiva por email + rota password (usa `db_connection.py`)

### Estado final de cuentas activas (10)
| Email | Rol |
|-------|-----|
| dtejedo@gmail.com | super_admin |
| superadmin@atlas.com | super_admin |
| test_utf8@atlas.com | admin |
| diego@humaniq.com.mx | admin |
| psaez@humaniq.com.mx | recruiter |
| xsanchez@humaniq.com.mx | recruiter |
| majo@humaniq.com.mx | recruiter |
| arosas@hqts.com.mx | recruiter |
| brangel@hqts.com.mx | recruiter |
| vguerrero@hqts.com.mx | recruiter |

**Adicional 2026-07-16:** `admin@atlas.com` también desactivada (cuenta huérfana de pruebas de marzo).

## 2026-09-29 — Pestaña "CV idénticos" (Fase 0 + Fase 1)
- Backup previo de Atlas: `/app/backups/backup_atlas_talent_vault_20260929_013814.archive.gz` (8.01 MB).
- Nuevo `backend/cv_hash_service.py`: SHA-256 de archivo y de texto extraído normalizado (hash de texto solo si >= 300 chars), colección `cv_hashes` (`active` marca CVs de fichas vivas).
- Backfill de 849 CVs (`scripts/cv_hash_backfill.py`): 3 errores de descarga (archivos ausentes en object storage, rutas legacy `uploads/resumes/...`) y 21 sin hash de texto.
- Detección: 150 grupos con CV idéntico / 185 fichas sobrantes (146 por hash de archivo, 4 por hash de texto). Informe en `/app/test_reports/identical_cv_groups.json`.
- Endpoints: `GET /api/duplicates/identical-cv`, `POST /api/duplicates/identical-cv/delete-extras` (solo admin, soft delete + `cleanup_audit_log`, copia campos faltantes a la ficha conservada). Conserva la ficha con clasificación aprobada por humano; si ninguna, la más antigua.
- Prevención en carga (los 3 flujos: individual, batch, update-cv): si el hash de archivo ya existe en cualquier candidato → bloqueo "CV ya cargado (candidato X)" sin crear ficha; `DuplicateKeyError` capturado con el mismo mensaje.
- Índice único global `uniq_active_sha256_file` (parcial sobre `active: true`): se intenta crear en cada arranque y tras cada limpieza; hoy NO se crea porque quedan 185 sobrantes activos pendientes de aprobación del usuario.
- Fusiones N-a-1 ahora transfieren los hashes al candidato primario; la limpieza de huérfanos desactiva los hashes.
- Frontend: `components/IdenticalCVTab.js` + pestañas en `pages/DuplicatesPage.js` (selección por grupo, "Seleccionar todos", eliminación en lote, botón "Fusionar N-a-1" para grupos con datos propios, "Revisar manual" sin borrado en lote).
- Corregido nombre mal parseado de la ficha `7ba8279c` → "Eliot Roaro".
- Pruebas: `backend/tests/test_identical_cv_flow.py` (grupo sintético: detección, soft delete, copia de campos, desactivación de hash y auditoría) y prueba manual de bloqueo al re-subir un CV existente (candidato Bernardo Baader).
- `git diff` vacío en `backend/scoring/` y `job_matching_service.py`.
- NADA eliminado: las 185 fichas sobrantes siguen activas esperando aprobación del usuario en la pestaña.

## 2026-09-29 (tarde) — Aviso con enlace + verificación de limpieza
- **La limpieza de sobrantes NO se ejecutó**: `cleanup_audit_log` no tiene ningún registro `identical_cv_cleanup`, 848 candidatos activos (sin cambios), 147 hashes de archivo con 2+ CVs activos y 181 CVs sobrantes. Índice `uniq_active_sha256_file` NO creado (solo `_id_`). Probable causa: los clics se hicieron en la app desplegada (producción), que aún no tiene este código; el preview sí lo tiene.
- Aviso inteligente: `existing_candidate` y `message` expuestos al frontend; botón "Ver ficha de {nombre}" en resultados de carga individual (`upload-result-identical-cv-link-{i}`) y en jobs de lote (`batch-job-identical-cv-link-{job_id}`). Los errores `identical_cv` del lote ahora incluyen `candidate_id`/`candidate_name`. Verificado en UI re-subiendo el CV de Bernardo Baader.
- Barrido por nombre (`scripts/duplicates_sweep_by_email.py`, solo lectura, estado actual SIN limpieza aplicada): 162 grupos / 368 fichas / 206 sobrantes → mismo email 155, emails distintos 1, sin email 6. Informe: `/app/test_reports/duplicates_sweep_by_email.json`.

## 2026-09-29 (noche) — Limpieza aplicada en producción + fixes
- Deploy exitoso tras desacoplar CORS de la clave del sistema: `cors_config.py` usa `HUMANIQ_CORS_ORIGINS` si existe; si `CORS_ORIGINS` llega como `*` usa lista explícita de respaldo (emergent.host + preview) con warning; sigue fail-closed ante comodines u orígenes mal formados.
- Limpieza ejecutada por el usuario en producción (22:55–22:56 UTC): 150 grupos procesados, **185 fichas desactivadas** (soft delete, `deletion_type: identical_cv_cleanup`), 146 fichas conservadas recibieron campos faltantes. Candidatos activos: 848 → **663**. `cv_hashes` activos: 846 → 662.
- Índice único **`uniq_active_sha256_file` CREADO** (parcial sobre `active: true`); ya no hay hashes de archivo repetidos entre CVs activos. Verificado además con inserción directa: MongoDB rechaza el duplicado (E11000).
- Fix: `group_key` era la raíz del union-find (no determinista entre llamadas) → los POST de limpieza podían devolver "grupo_no_encontrado" y 0 eliminaciones. Ahora `group_key` = menor `file_path` del grupo, la respuesta incluye `file_paths` y el endpoint acepta también cualquier `file_path` del grupo como clave.
- UI: si `deleted_count` es 0 el toast ahora avisa en lugar de mostrar éxito.
- Barrido por nombre tras la limpieza: 23 grupos / 48 fichas / 25 sobrantes (mismo email 21, emails distintos 1, sin email 1). Informe: `/app/test_reports/duplicates_sweep_by_email.json`.

## 2026-09-29 (cierre) — Eliminar en duplicados, Papelera, caducidad de vacantes y dashboard clickeable
- **Eliminar en Duplicados**: `POST /api/duplicates/delete-candidates` (solo admin, soft delete + `cleanup_audit_log`, desactiva hashes). Botón por ficha (`delete-candidate-{id}`), "Eliminar grupo (sobrantes)" (`delete-group-extras-btn`) y por ficha en la pestaña CV idénticos (`identical-cv-delete-member-{id}`). Si la ficha tiene notas, asignaciones (`job_assignments` o colección `assignments`) o `cv_versions` → se bloquea y el aviso propone fusionar N-a-1.
- **Papelera** (`/trash`, solo admin, enlace en sidebar): `GET /api/trash/candidates` con fecha, quién eliminó y motivo; "Restaurar" en un clic reusando `POST /api/candidates/{id}/restore`, que ahora limpia `deletion_type/deletion_reason/duplicate_of` y reactiva los hashes salvo colisión con el índice único.
- **Vacantes — caducidad y archivo**: nuevo `job_lifecycle_service.py` (90 días sin actividad, aviso 7 días antes). `JobStatus.ARCHIVED` + campos `last_activity_at/archived_at/archived_by/archive_reason/auto_archived`. Endpoints `POST /api/jobs/{id}/archive`, `/reactivate`, `GET /api/jobs/expiring`, `GET /api/jobs/similar-archived`, `POST /api/jobs/{id}/reuse-candidates`. `GET /api/jobs` excluye archivadas salvo `status=archived`. UI: "Ver archivadas", botones Archivar/Reactivar, diálogo de archivadas similares al crear vacante con reutilización de candidatos en un clic. Las archivadas conservan candidatos, etapas y notas (verificado).
- **Cron**: `.emergent/crons.yml` → `archive-stale-jobs` diario 07:00 UTC contra `POST /api/cron/archive-stale-jobs` (bearer `WEBHOOK_CRON_SECRET`, idempotente por `run_id`, ack inmediato y trabajo en background).
- **Dashboard clickeable**: las 6 tarjetas de KPI navegan a su lista filtrada (`/candidates`, `/jobs`, `/candidates?created_from=`, `/review`, `/candidates?placed=true`); bandeja "sin vacante" → `/candidates?unassigned=true`; nuevo bloque "Vacantes por caducar". `GET /api/candidates` acepta `placed`, `unassigned`, `created_from`. Corregido bug previo: `dashboard/stats` contaba vacantes con `status: "open"` (inexistente) en lugar de `active`.
- Pruebas: `backend/tests/test_duplicates_trash_jobs_cycle.py` 10/10 OK; testing agent de frontend 100% (KPIs, alerta de caducidad, archivar/reactivar, botones de eliminar con confirmación, CV idénticos, papelera con búsqueda y restaurar). El diálogo de archivadas similares se validó por backend (no en UI: no había vacantes archivadas reales).
- `git diff` vacío en `backend/scoring/`, `job_matching_service.py` y `affinity_matrices.py`.
- Pendiente de tu aprobación: fusión N-a-1 de los 21 grupos con mismo email, en tandas de 5. Ninguna fusión ejecutada.

## 2026-09-29 (fusión por email) — 21 grupos fusionados N-a-1
- Backup previo: `/app/backups/backup_atlas_talent_vault_20260929_233815.archive.gz` (8.27 MB).
- Script `scripts/merge_email_duplicates.py` (tandas de 5): 21/21 grupos fusionados, 23 fichas secundarias desactivadas, 0 saltados. Candidatos activos 663 → 640; papelera 274 → 297.
- Principal = ficha más antigua; `keep_all_cvs=True`: los 21 principales conservan CVs históricos (versiones o múltiples archivos). Notas y asignaciones preservadas por `CandidateMerger`.
- Sin tocar: 1 grupo con emails distintos y 1 grupo sin email (quedan listados para revisión manual).
- Barrido final por nombre: 2 grupos / 4 fichas / 2 sobrantes. Informe: `/app/test_reports/email_merge_batches.json`.

## 2026-10-01 — Casos restantes, calidad de nombres y alerta de duplicados
- Backup previo: `/app/backups/backup_atlas_talent_vault_20261001_010639.archive.gz` (8.30 MB).
- Carlos Sunderland Silva fusionado N-a-1 con principal `397044de` (Commercial Director); 2 CVs como versiones + nota con el correo alterno `carlos@stillworksbrands.com`.
- Fichas "No especificado" corregidas como personas independientes: `aa5ee578` → César Reynoso Chávez (+ email y teléfono del CV) y `8e54901a` → Javier Gamero Compeán.
- **Barrido de calidad de nombres** (`scripts/name_quality_scan.py` + `name_fix_proposals.py` con lectura del CV y parseo AI): 37 fichas detectadas → 15 nombres reales corregidos (acentos preferidos del CV cuando la IA los perdía) y 22 fichas sintéticas de QA eliminadas (soft delete) con sus 22 CVs purgados. Activos: 639 → **617**. Barrido final: 0 nombres sospechosos.
- `storage_service.delete_object()`: el object storage de la plataforma **no soporta DELETE (405)**, así que la purga sobrescribe el objeto con 0 bytes (contenido irrecuperable) y se quita la referencia de la ficha.
- **Validación al cargar** (`name_quality.py`): si el nombre resulta placeholder, nombre de archivo, con caracteres inválidos, una sola palabra, todo mayúsculas/minúsculas o demasiadas palabras → la ficha entra a "Por Revisar" con `review_status='manual_capture'`, mensaje "Nombre dudoso" y `name_quality_issues`. Aplicado en carga individual y en lote, y re-aplicado después de la clasificación AI para que no la sobrescriba. Verificado end-to-end subiendo un CV sin nombre legible.
- **Alerta de duplicados en el dashboard**: `duplicates_alert` en `GET /api/dashboard/operational` (grupos, fichas, nuevos de 7 días, grupos de CV idéntico) + filas en "Mi bandeja" con badge naranja de nuevos. Hoy: 3 grupos / 6 fichas / 0 nuevos / 0 CV idénticos.
- `git diff` vacío en `scoring/`, `job_matching_service.py` y `affinity_matrices.py`.

## 2026-10-07 — Modelos Claude actualizados, selector por tarea y Análisis IA del match
- **Modelos actualizados** (vía emergentintegrations + Emergent LLM Key): parseo de CV, clasificación, parseo de vacante y match textual → `claude-sonnet-5-5`; resumen ejecutivo (alto volumen) → `claude-haiku-4-5-20251001`; análisis de match → `claude-opus-5-5`. Antes todo era `claude-sonnet-4-5-20250929`.
- **Selector por tarea** (`ai_model_config.py`, colección `ai_model_config`, caché de 60 s): `GET /api/admin/ai-models` y `PUT /api/admin/ai-models` (solo admin, valida tarea y modelo). Nueva UI en `/admin` con un selector por proceso, botón "Valores recomendados" y aviso de cambios sin guardar. 6 modelos disponibles de Opus 5.5 a Haiku 4.5.
- **Análisis IA del match** (`ai_match_review_service.py`, solo lectura sobre el motor): toma el ranking de `job_matching_service.match_candidates` y Claude Opus 5.5 devuelve por candidato fit alto/medio/bajo, veredicto, fortalezas, brechas, preguntas de entrevista y riesgos, más un resumen de la terna y consejo de búsqueda. Endpoints `POST/GET /api/jobs/{id}/ai-match-review`, persistido en `ai_match_reviews`. UI: panel `AIMatchReview` en el detalle de vacante (se recarga el último análisis guardado).
- El payload a Claude incluye todo el contexto real de la vacante (objetivo, contexto del rol, responsabilidades, experiencia requerida, no negociables, scorecard, ubicación, modalidad, salario) para que el criterio sea específico.
- Verificado: carga de CV end-to-end con los modelos nuevos (nombre, email, teléfono, industria, área/subárea, seniority, 11 skills y resumen correctos), análisis de match en la vacante "Director Comercial" (detectó que ningún finalista tiene telecom ni retención B2C y propuso de dónde buscar), cambio de modelo persistente y rechazo de modelos no válidos (400).
- `git diff` vacío en `scoring/`, `job_matching_service.py` y `affinity_matrices.py`.
