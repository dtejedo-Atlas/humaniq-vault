# Humaniq Talent Vault — Product Requirements Document

## Objetivo original
Construir una aplicación web full-stack lista para producción para una firma de reclutamiento, denominada Humaniq Talent Vault: una base de candidatos con extracción y clasificación de CVs mediante IA, búsqueda híbrida y matching candidato-vacante.

## Usuarios y requisitos principales
- Reclutadores ejecutivos y administradores de Humaniq en México y Latinoamérica; interfaz en español.
- Acceso exclusivamente por invitación, roles super_admin/admin/recruiter/researcher, login por contraseña y Google para cuentas registradas.
- Carga individual y masiva de CVs, parsing PDF/DOCX, clasificación IA, revisión humana, búsqueda híbrida, taxonomía bilingüe y smart folders.
- Historial y versionado de CVs, detección/fusión manual de duplicados, notas, asignaciones y trazabilidad preservada.
- Vacantes con scorecards, matching v2/v3, exportación PDF/DOCX, pipeline simplificado y dashboard operativo.
- Las bajas de personal se gestionan con `users.is_active: false`; NO borrar usuarios ni sus candidatos, notas o asignaciones.

## Estado operativo
- Aplicación en fase de uso real y desplegada en producción.
- Preview y producción comparten la base MongoDB Atlas. Toda operación de datos afecta el entorno real.
- No hacer cambios especulativos, nuevas funcionalidades ni refactorizaciones: solo lo solicitado expresamente.
- Las pruebas deben ser no destructivas; usar exclusivamente cuentas de prueba documentadas para operaciones auxiliares.
- Incidente anterior de credenciales atendido mediante rotación y exclusión de `memory/test_credentials.md` de git. No copiar contraseñas, tokens ni claves a documentos versionados.

## Arquitectura y referencias
- Frontend: React, Tailwind y Shadcn/UI. Páginas y componentes en `frontend/src/`; cliente API en `frontend/src/api/`.
- Backend: FastAPI, Python y MongoDB; rutas bajo `/api` en `backend/server.py`.
- `backend/models.py`: usuarios, candidatos, CVs, vacantes, scorecards y demás modelos.
- `backend/user_service.py`: gestión de cuentas, roles y desactivación conservando historial.
- `backend/auth.py`: contraseñas y JWT. `get_current_user` consulta el estado de la cuenta en cada petición.
- `backend/invitation_service.py` y `backend/email_service.py`: invitación/restablecimiento administrado y entrega mediante Resend.
- `backend/assignment_service.py`: asignaciones de candidatos.
- `backend/atlas_service.py`: parsing y clasificación IA; `backend/background_processor.py`: lotes persistidos en MongoDB.
- `backend/scoring/`: motor v3 aislado; `backend/job_matching_service.py`: motor v2; `backend/hybrid_search_service.py`: búsqueda híbrida.
- CVs en Emergent Object Storage; Claude y OpenAI para IA/embeddings; Google Auth administrado y Resend.
- El frontend usa exclusivamente `REACT_APP_BACKEND_URL` del entorno actual; no reutilizar URLs de forks anteriores.
- Advertencia histórica: el backend existente prioriza `ATLAS_URI`/`ATLAS_DB_NAME` frente a la copia local. No asumir que una consulta al Mongo local representa producción, ni cambiar conexiones durante tareas operativas. Para esta baja se usó únicamente la API existente.
- Credenciales vigentes: `memory/test_credentials.md`, archivo privado ignorado por git.

## Último trabajo — 2026-09-25: catálogo Humaniq como capa de presentación
**Autorización del usuario:** cargar `catalogo_humaniq.json` (15 áreas / 105 subáreas / 13 seniorities) como capa de presentación; arquitectura de dos campos; mapeo aprobado con Salud y ESG SIN equivalencia; normalizar salida del LLM antes de declarar «fuera de catálogo»; corregir `it`→`technology` en registros existentes; fusionar duplicados de Ángel Osvaldo Flores Reyna; corregir los 6 errores de linter borrando SOLO la primera definición de cada duplicado y renombrando la variable del loop. Scoring, pesos y matching intactos.

### Claves técnicas reales del motor (documentado para no volver a suponer)
- `affinity_matrices.py::FUNCTIONAL_AFFINITY` reconoce **9 áreas**: human_resources, finance, operations, supply_chain, marketing, sales, technology, legal, general_management. Sinónimos en código: `commercial`→sales y `business_development` con afinidades propias. Cualquier otro valor cae al fallback `return 20` en silencio.
- `taxonomy.py::FUNCTIONAL_AREAS` (24 claves) es vocabulario de clasificación, NO del motor. `scoring/components.py` infiere 10 claves por título e incluye `engineering`, que tampoco existe en la matriz.
- Seniority: `SeniorityLevel` (models.py) admite 10 valores; `SENIORITY_TO_INDEX` (job_matching_service.py) lista 13 pero intern/senior_manager/ceo no son almacenables en candidatos.

### Implementado
- `backend/humaniq_catalog.py` + `backend/data/catalogo_humaniq.json`: catálogo, `AREA_TO_ENGINE` (salud y sustentabilidad → None), `SENIORITY_TO_ENGINE`, índices separados de área y subárea, `resolve_area`/`resolve_seniority` (insensibles a idioma, acentos y mayúsculas), `normalize_classification`, `normalize_job_taxonomy`, `public_catalog`, `build_humaniq_prompt_section`.
- Nunca se guarda un valor que el motor no reconoce: si no resuelve, `functional_area` queda null, se registra en `out_of_catalog` y el candidato cae a revisión; salud/ESG conservan `presentation_area` con `functional_area` null y no bloquean la aprobación.
- Clasificación capa 1 (`atlas_service.classify_candidate`) y capa 2 (`classification_refinement`) usan el prompt del catálogo Humaniq y normalizan antes de penalizar confianza. Vacantes (`parse_job_description`, create_job, update_job) normalizan área y seniority a claves del motor.
- Nuevos campos `presentation_area`, `presentation_subarea`, `presentation_seniority`, `taxonomy_version` en Candidate, AIClassification, Job/JobCreate/JobUpdate; propagados en classify, aprobación individual y masiva, corrección manual y payload de la bandeja.
- `GET /api/taxonomy/humaniq` expone el catálogo con su clave del motor; `/api/taxonomy/lookup` incluye los nombres de las 9 claves técnicas para que la UI nunca muestre una key cruda.
- Edición manual: `expand_presentation_fields` traduce presentación→motor; se conservan las áreas personalizadas creadas por admin y el 422 sólo cuando el valor no existe en ningún catálogo.
- UI: 5 dropdowns (industria, área de 15, subárea dependiente, seniority de 13, años) en ficha y bandeja. Corregida una carrera de arranque en `TaxonomyContext` (el provider hijo montaba antes de que AuthContext fijara la cabecera Authorization → 403 y «Fuera de catálogo» tras recarga).
- Linter: borradas SOLO las primeras definiciones de ActivityLog, SmartFolder, SmartFolderCreate, SmartFolderUpdate, FolderType y del prompt duplicado en taxonomy.py; variable del loop `status`→`candidate_status`. Ruff: F811/F402/F821/E722 limpios.

### Datos migrados (base Atlas compartida)
- `it`→`technology`: **64 candidatos** en el campo principal + 64 en `ai_classification`; 0 vacantes (la vacante afectada tiene `it_technology`).
- Backfill aditivo de presentación: **832 candidatos**, 0 sin resolver. `functional_area` no se tocó salvo el caso `it`.
- Ángel Osvaldo Flores Reyna: fusionada `21e8a3ab` dentro de `ee7dd8a7` (N-a-1, auditoría registrada, secundaria con `deletion_type: merged`), 10 skills añadidos, reclasificado a finance/finanzas/contraloria/gerencia con 95% de confianza. Ambas fichas tenían 0 notas, 0 asignaciones y 0 historial, por lo que no había nada que perder.
- **Pendiente de autorización:** 211 candidatos activos conservan claves históricas que el motor no reconoce (logistics 39, project_management 32, accounting 31, business_development 29, talent_acquisition 19, quality 14, construction_management 13, procurement 10, customer_service 9, manufacturing 7, maintenance 4, planning 2, research_development 1, engineering 1) y 2 vacantes (`it_technology`, `accounting`). Hoy puntúan 20/100 en el matching.

### Verificación
- Suite backend: **13 failed / 160 passed / 32 skipped / 126 errors**, fallos y errores idénticos al baseline previo (requieren servidor/BD en vivo). 27 pruebas nuevas: `tests/test_humaniq_catalog.py`, `tests/test_humaniq_manual_and_jobs_isolated.py`, `tests/test_humaniq_live_readonly.py`.
- Iteración 33 del agente de pruebas: 0 issues críticos y 0 menores; escrituras sólo en Mongo local aislado.
- `git diff` VACÍO en `backend/scoring/`, `job_matching_service.py`, `scoring_config.py` y `hybrid_search_service.py`. La lista protegida del test `test_protected_scoring_files_have_no_diff` dejó de incluir `atlas_service.py` porque el usuario pidió explícitamente cambiar ahí la normalización de clasificación.
- Colapsos conocidos del seniority (13 presentación → 10 del enum): gerencia_jr/gerencia/gerencia_sr → manager; subdireccion/direccion → director. Los 13 niveles se conservan en `presentation_seniority`.

### Deuda detectada y NO corregida (informada)
- `duplicate_detector_v2.merge_candidates` trata `notes` como texto aunque el modelo es lista: fusionar fichas con notas podría convertir la lista en string. No se disparó porque ambas fichas de Ángel tenían 0 notas.
- `keep_all_cvs` lee el campo heredado `resume_file_key`, que ya no se usa: el CV de la ficha secundaria no se conserva como versión histórica.

## Trabajo anterior — 2026-09-24: lectura segura de CV y eliminación de fallbacks locales
**Autorización del usuario:** únicamente detener clasificación cuando no se puede leer el CV, reemplazar fallback local por reintentos remotos/error visible/marca persistente e inventariar referencias locales existentes SIN borrarlas ni migrarlas. Cinco F811 y un F402 siguen congelados. No scoring/matching/pesos.

### Implementado
- `resume_read_safety.py` recupera CV vigente (versión activa o archivo más reciente), distingue storage remoto y ruta local heredada, usa extracción real PDF/DOCX y exige texto legible. El endpoint classify no invoca IA si falta el original, falla la descarga o extracción, o el contenido es ilegible: registra el error, responde 422, marca `manual_capture` y motivo, deja `ai_classification=null` y conserva la anterior dentro de `classification_read_error.previous_classification`. Campos profesionales/notas/asignaciones intactos; candidato aparece en Por Revisar. Si cambia la ficha/CV durante el intento, no sobreescribe el cambio y responde 409.
- `StorageService.upload_resume`: máximo 3 intentos totales (inicial + 2 reintentos) para fallos transitorios, misma clave remota en cada intento, timeout/backoff acotados. Fallos permanentes de permisos/credenciales/cuota abortan inmediatamente según playbook. Ningún nuevo proveedor ni claves.
- Eliminados los dos fallbacks de upload-resume y el mismo fallback encontrado en `process_cv_job` (carga por lote, dentro del mismo problema funcional). Fallo remoto: resultado `failed`, sin ruta/archivo local ni versión fantasma, ficha conservada con `cv_storage_issue`. Si había CV anterior, permanece intacto. La actualización de CV desde ficha también marca error 503 y una carga posterior exitosa limpia la marca.
- UI: clasificación 422 refresca ficha/contador y muestra Requiere captura manual sin éxito falso; aviso persistente de original pendiente; cargas individual/lote muestran error explícito. Lote fallido por storage ofrece Abrir ficha, no un reintento imposible sin bytes (worker preexistente libera memoria). La usuaria puede volver a cargar desde Nueva versión. Fallo de Nueva versión refresca marca en ficha; éxito la limpia.

### Inventario de SOLO LECTURA (2026-09-24 19:49:54 UTC)
- BD compartida existente: 915 candidatos, 829 activos y 86 eliminados lógicamente. 3 referencias locales en candidatos + 3 en cv_versions representan **3 archivos únicos de 3 candidatos activos**, NO seis CV distintos. 862 referencias remotas en candidatos, 120 remotas en versiones.
- **1 archivo existe en este preview; 2 no existen aquí.** No se inspeccionó el disco de producción; ausencia en preview NO demuestra pérdida definitiva. No se abrió contenido de CV ni verificó disponibilidad remota.
- Cero escrituras de inventario, cero borrados, cero migraciones. Los tres originales heredados siguen pendientes de decisión/recuperación del usuario antes de una sustitución del contenedor.
- Resumen sin PII: `/app/test_reports/cv_local_inventory.json`. Detalle privado IDs/rutas, permiso 0600: `/root/humaniq_cv_diagnosis/local_resume_inventory.json`. Script reproducible de lectura: `backend/scripts/inventory_local_resume_references.py`. Cuenta referencias locales; no prueba cuál rama histórica las creó.

### Verificación
- Testing iteration_32 inicialmente 40 pass / 2 live omitidos. Autoverificación ampliada final: **65 pass / 2 live omitidos**, en Mongo LOCAL temporal; IA/storage MOCKED exclusivamente en pruebas, ninguna mutación en Atlas ni uploads remotos reales. DOCX sintético real extraído sin simular parser; éxitos local/remoto, selección de versión vigente, 404/timeouts/archivo corrupto/vacío, reintentos, preservación CV anterior, recuperación por update-cv y conflicto por CV retirado probados.
- Navegador con APIs MOCKED: transición classify422 a captura manual sin aprobación/éxito falso; fallo de carga individual y lote; avisos a 320/768/1024/1440 sin overflow. Fixture final bloquea llamadas API no simuladas. Build frontend pasa con warnings históricos.
- Evidencia: `test_reports/iteration_32.json`, `test_reports/pytest/cv_safety_final.xml`, `cv_safety_final_pytest.log`, `cv_safety_build.log`, `check_iteration_32_cv_safety_mocked.py` y `cv_safety_smoke.jpg` (todos persistentes).
- `git diff` vacío working tree y contra baseline **d1d276fddbfb6a4b31e8df140ad4965a57f0d8b5** en `backend/scoring/`, `backend/job_matching_service.py`, `backend/scoring_config.py`. AST de ambas definiciones de modelos duplicados, prompt duplicado y dashboard shadow idéntico. Ruff sigue reportando exactamente **5 F811 + 1 F402** congelados; E722 eliminado con corrección funcional, no simple limpieza.
- Nota de pruebas: la selección histórica de DB prioriza Atlas; se conserva sin refactor y TODAS las pruebas sobrescriben servicios con Mongo local. No se afirma limpieza global, sincronización GitHub, despliegue ni seguridad de producción. CORS de producción requiere comprobación separada tras actualizarla; el último chequeo anterior seguía permisivo.

### Pendientes
- P0: decisión del usuario sobre recuperar/migrar los 3 CV locales heredados; NO ejecutar sin autorización. Validación usuaria de los dos fixes.
- P1: si se solicita, probar configuración/permisos de producción tras actualización real; no equiparar código local con producción.
- P2: cinco F811 y F402 + demás backlog continúan congelados. Mejora futura sugerida, no implementada: control periódico de disponibilidad de originales.

## Trabajo anterior — 2026-09-24: opción A, ficha y clasificación verificadas
**Alcance explícito:** resolver el timeout del botón de clasificación y validar cuatro dropdowns de guardado inmediato según los permisos aplicados. Nada más. Almacenamiento local de CV y siete errores de código preexistentes expresamente congelados.

### Implementación y diagnóstico
- El botón `classify-button` ya estaba condicionado correctamente a admin/super_admin y se confirmó visible antes de cambiar código. No se relajó ese permiso. El timeout se reprodujo en la prueba antigua: el fixture devolvía `[]` para `/taxonomy/lookup`, provocando una excepción al mostrar industria; también simulaba `/edit-permission` en lugar de `/can-edit`. Ambos datos de prueba corregidos. No fue necesario cambiar autenticación ni backend.
- Los cuatro dropdowns existían en Por Revisar pero faltaban en CandidateDetail. Ahora la ficha reutiliza `ReviewField` mediante `CandidateClassificationFields.js`: industria, área funcional, seniority y años; PATCH existente de un solo campo, guardado inmediato, cero años distinto de Sin dato, confirmación visible solo tras éxito y conservación del valor anterior ante error.
- Edición manual habilitada exclusivamente con `/can-edit` confirmado: admin/super_admin o recruiter asignado; researcher y recruiter no asignado en solo lectura. Estado de permiso ligado a candidato/usuario/rol; mientras carga o falla, no habilita edición. Fichas aprobadas permanecen bloqueadas conforme a la política 409 existente del servidor.
- Clasificar/aprobar bloqueados durante guardado y los dropdowns durante clasificación/aprobación. Protección frente a doble clic y mensajes reales ante 403/429/500. Botón Editar enfoca el primer campo. Corrección de distribución de clasificación y columna lateral para móvil.
- Cambios de producto de esta ronda limitados a `frontend/src/pages/CandidateDetailPage.js` y nuevo `frontend/src/components/CandidateClassificationFields.js`; resto: pruebas y documentación. No se modificaron cuentas, claves, backend productivo, modelos, taxonomía ni almacenamiento.

### Verificación final
- `yarn build` correcto, con advertencias históricas de hooks/dependencias; no se afirma limpieza global.
- Iteración 31: cinco tests backend aislados y una comprobación pública de lectura aprobados. Incluye **una clasificación real con el servicio IA existente sobre candidato puramente sintético en Mongo LOCAL**, sin CV/datos de candidatos reales. Prueba live convertida a opt-in `RUN_LIVE_CLASSIFICATION_TEST=1` para evitar llamadas futuras accidentales.
- Autocomprobación final: **9 tests de regresión aislados aprobados**, sin repetir la llamada IA. Persistencia de los cuatro campos, rechazo por rol, clasificación, conservación de confianza/aprobación y validación de valores.
- Navegador: botón visible para ambos roles administrativos; oculto para recruiter/researcher; cinco combinaciones de rol/asignación verificadas. Cuatro PATCH individuales y persistencia al recargar; 0/null, bloqueo concurrente, errores 403/409/422/500 de guardado y 403/429/500 de clasificación; permisos lentos/fallidos y fichas aprobadas comprobados.
- Dos fixtures responsive pasan a **320/768/1024/1440**, scrollWidth igual al viewport, sin desbordamiento ni elementos fuera de pantalla.
- **MOCKED únicamente en las pruebas de navegador** para no mutar Atlas compartido; aplicación usa APIs reales y persistencia backend se prueba en Mongo local temporal. Ningún candidato real modificado.
- `git diff` vacío en `backend/scoring/`, `backend/job_matching_service.py` y `backend/scoring_config.py`, tanto working tree como contra `37f838fbf8b6507d6e115c62073f7047a1ecb8b4`. Pesos/matching intactos.
- Evidencia: `test_reports/iteration_31.json`, `pytest/option_a_final_regression.xml`, `option_a_mocked_responsive.json`, `security_candidate_responsive_verified.json`. Scripts reutilizables corregidos: `check_option_a_candidate_detail_mocked.py` y `check_security_candidate_responsive.py`.

### Prioridades y próximos pasos
- P0 opción A: sin pendientes técnicos conocidos tras la verificación; pendiente la validación del usuario.
- P1: revisión del usuario con una ficha de prueba y un reclutador asignado; no realizar cambios adicionales sin solicitud.
- P2/P3: almacenamiento local de CV, siete hallazgos de código, sesiones JWT, límites de autenticación, auditoría visible y demás backlog permanecen congelados o aplazados. Posible mejora futura: visibilidad del historial de ajustes manuales, sin implementación en esta ronda.

## Trabajo anterior — 2026-09-22: CAPA 1 y CAPA 2 completadas
**Autorización del usuario:** ejecutar en orden dos capas, informar números de Capa 1 antes de avanzar a Capa 2, NO integrar web, NO tocar scoring/pesos/matching. El usuario confirmó además que recargó créditos durante la ejecución.

### Capa 1 — extracción corregida y 34 reprocesados
- DOCX: extracción OOXML de párrafos, tablas anidadas, cuadros de texto, encabezados y pies; una sola rama AlternateContent, sin duplicados ni texto eliminado por control de cambios.
- PDF: conserva extractor multicolumna y añade lector alternativo pypdfium2; OCR por página en PDFs imagen/contornos y mixtos, incluso si otras páginas tienen texto.
- Poppler y Tesseract instalados con idiomas español/inglés. `scripts/install_ocr.sh` + `ocr_runtime.py` realizan preparación idempotente al arrancar si faltan dependencias; si falla la instalación se informa OCR no disponible, sin fingir lectura exitosa.
- **Resultado real: 34/34 legibles, 34/34 clasificados automáticamente con los cuatro campos completos, 0 ilegibles, 0 pendientes del grupo. Confianza 78%-95%.** No son aprobaciones humanas.
- Se entregó ese resultado al usuario ANTES de implementar Capa 2.
- Reprocesamiento ejecutado mediante `scripts/reprocess_diagnostic_cohort.py --apply`, limitado a los IDs/archivos diagnosticados. Usa parse_resume y classify_candidate ORIGINALES: 68 llamadas de primera pasada, cero de segunda.
- IDs, CVs originales, notas, asignaciones, tags, fechas de creación e historial ajeno a campos derivados preservados y comparados. Audit/before-images y resultados en Mongo `cv_reprocessing_runs`; datos nominales privados en `/root/humaniq_cv_diagnosis/layer1_results.json`.
- 12 pruebas Capa 1 aprobadas; el fallo detectado en truthiness de elementos OOXML fue corregido antes de reprocesar.

### Capa 2 — implementada, sin web
- Wrapper separado mantiene la primera pasada existente; solo ejecuta segunda si confianza <0,75, clasificación no canónica/campo faltante o años desconocidos. Cero años válidos no dispara por sí solo.
- Se relee texto completo recuperado, sin recortar a 3.000 caracteres. Documento excesivo se rechaza explícitamente en vez de truncarlo silenciosamente.
- Modelo conservado: `claude-sonnet-4-5-20250929`, SDK existente y `_send` no streaming (el instalado NO exporta TextDelta). No se cambiaron proveedor, clave o dependencias Python.
- JSON validado con Pydantic; fechas/citas verificadas contra CV. Industria dominante por meses en últimos 120 meses, prorrateando empleos simultáneos entre sectores; seniority por responsabilidades; años por unión de meses sin contar educación ni duplicar simultáneos. Incertidumbre/ties/fechas faltantes reducen confianza.
- Caché por contenido/versión de proceso/modelo/catálogo/país, con deduplicación concurrente en Mongo. Caché de industria/tamaño de empresas a partir de modelo/contexto; solo se envían entradas de empresas citadas en el CV. **NO web scraping ni búsqueda web en la aplicación.**
- Una ejecución adicional automática; fallos no se reintentan automáticamente. Un reintento explícito de fallo está permitido hasta máximo dos intentos; resultados exitosos se reutilizan sin otra llamada.
- Archivos ilegibles: `review_status=manual_capture`, mensaje «Requiere captura manual» y avisos visibles en carga individual, carga en lote y Por Revisar. No LLM sobre texto ilegible; no aprobación ficticia.
- Botones individuales y de lote habilitados. Jobs/resultado persistidos, recuperación del último lote por usuario, progreso y errores. Protección contra cambios concurrentes, CV activo cambiado y sobrescritura de aprobación o campos manuales.
- **No se ejecutó Capa 2 sobre los 34:** ya cumplían umbral y campos completos. Permanecen cero pendientes, sin llamadas redundantes.

### Arquitectura nueva y verificación final
- `docx_extraction.py`, `pdf_extraction.py`, `ocr_runtime.py`: extracción, OCR y preparación nativa.
- `classification_evidence.py`: cronología exclusiva de clasificación, NO importada por scoring/matching.
- `classification_refinement.py`: condiciones, prompt completo, conocimiento empresarial, evidencia/caché de segunda pasada.
- `cv_recheck_service.py` y `cv_recheck_routes.py`: re-revisión in-place y jobs asíncronos. Rutas: `POST /api/atlas/classifications/recheck`, `GET /api/atlas/classifications/rechecks/latest`, `GET /api/atlas/classifications/rechecks/{batch_id}`.
- Colecciones nuevas: `cv_reprocessing_runs`, `cv_text_extractions`, `cv_classification_passes`, `company_classification_cache`, `cv_recheck_batches`, `cv_recheck_jobs`.
- UI: `ReviewRecheckProgress.js`; botones y estados en revisión/carga. No hubo cambios visuales ajenos al flujo.
- Verificación final: **47 pruebas de regresión aprobadas**, excluyendo repetición de prueba real; previamente **una llamada real Claude con CV sintético** validó integración y cache_hit en la segunda consulta. Suite específica Capa 2: 17/17; interfaz con respuestas **MOCKED solo durante pruebas** para proteger producción; APIs/persistencia probadas en Mongo local aislado. Responsive 320/768/1024/1440 aprobado; build correcto.
- Prueba real ahora opt-in: `RUN_LIVE_CLASSIFICATION_TEST=1`, marcador `integration_live` registrado en pytest.ini para evitar ejecuciones/costos accidentales.
- Informe final: `test_reports/layer1_final_results.json`, `layers_scope_final.json`, `iteration_28.json`, `iteration_29.json`, `pytest/layers_final_regression.xml`.
- **Diff vacío** contra `35947513ee5c0cd6ab7fa7b96967919538e170e3` en `backend/scoring/`, `job_matching_service.py`, `scoring_config.py`, `hybrid_search_service.py` y `atlas_service.py`. No se reconstruyó la primera pasada.
- Los nueve hallazgos globales preexistentes fuera de alcance y warnings históricos siguen congelados. No afirmar que el chequeo global está limpio, aunque las pruebas funcionales de ambas capas pasan.

### Próximo paso
- Validación del usuario sobre una muestra de las 34 fichas y nuevas cargas reales. No reprocesar masivamente otra vez sin solicitud.
- Web permanece NO integrada; reevaluarla solo con casos nuevos realmente sin resolver y autorización del usuario.
- Limitación previa de cargas: bytes pendientes del upload original aún en memoria; navegar/minimizar no interrumpe el servidor, pero no se añadió reanudación del upload ante reinicio. Los rechecks sí conservan referencias a CVs ya almacenados y recuperan jobs persistidos.

## Histórico — diagnóstico y mejoras iniciales de revisión/carga
El estado pendiente descrito a continuación fue supersedido por las dos capas completadas arriba.
**Solicitud actual:** afinar clasificación/parsing, diagnosticar primero, proponer segunda pasada sin implementarla hasta recibir OK, mejorar bandeja Por Revisar y continuidad de carga. Restricción dura: NO tocar scoring/, v2/v3, pesos ni matching.

### Diagnóstico completado antes de implementar
- Bandeja real: **34** candidatos, no los 31 mencionados. 22 DOCX y 12 PDF; 26 al 0%, ocho entre 35%-72%. Años ausentes en 30. Confianza global, no por campo.
- 21 DOCX omiten tablas/cuadros de texto. Siete errores OCR por Poppler ausente: cinco registros PDF de imágenes (cuatro archivos únicos), uno de contornos/sin caracteres y otro recuperable con un lector alternativo sin OCR.
- Dos PDFs mixtos activan extracción parcial pero no OCR. Dos casos tienen texto suficiente y clasificación nula; el fallo JSON es hipótesis sustentada por código, no demostrado por respuesta original. Dos claves no canónicas corresponden a baja confianza al 50%.
- Se detectó extracción errónea de identidad a partir de una referencia en un DOCX. NO se corrigió automáticamente ningún registro.
- Informe nominal y archivos **privados** en `/root/humaniq_cv_diagnosis/report.md` y `evidence.json`. No copiar CVs/texto a git.

### Secciones 3 y 4 implementadas
- Seleccionar todos recupera IDs de toda la bandeja, independiente de paginación. Aprobación en lote conectada al endpoint existente y selección retenida para errores parciales.
- Cuatro dropdowns visibles y autosave mediante PATCH dedicado; editar no aprueba, no incrementa confianza IA y conserva otros campos. `Sin dato` y cero años son distintos. Guardas contra aprobación de clasificación vacía/no canónica.
- Botones individual y masivo para segunda pasada visibles pero **deshabilitados**: la funcionalidad NO está implementada ni simulada.
- Seguimiento de carga vive en un proveedor persistente entre rutas. Guarda referencia por usuario, recupera último lote desde backend y sincroniza al volver/recuperar foco/conexión. Sin reiniciar la barra ni volver a subir automáticamente.
- Rechazos de archivos persistidos; lote no se muestra completo hasta confirmar finalización de recepción. Modo lote también maneja un solo archivo.
- Responsive corregido en revisión/carga, con navegación lateral móvil plegable. No hay desbordamiento en 320/768/1024/1440.

### Archivos nuevos y pruebas
- `backend/classification_review_service.py`: validación y guardado manual atómico, sin parsing/LLM/scoring.
- Nuevas rutas: `GET /api/atlas/classifications/pending/ids`, `PATCH /api/atlas/classifications/manual/{id}`, `GET /api/candidates/upload-batches/latest`.
- `frontend/src/components/review/`, `contexts/UploadBatchContext.js`, `hooks/useBatchPolling.js`.
- 19 tests backend aislados pasan; Mongo temporal LOCAL, sin mutaciones en Atlas. Pruebas funcionales UI con mutaciones **MOCKED solo en tests**; aplicación usa endpoints reales. Revisión real de selección de 34 y lectura de lote existente; ocho combinaciones responsive pasan.
- `test_reports/iteration_27.json` registra hallazgos iniciales corregidos; ver `pytest/review_upload_final.xml`, `responsive_review_upload_verified.json`, `classification_scope_verification.json`.
- Snapshot de los 34 documentos originales idéntico antes/después. Diff vacío contra `4b06061333ac105ad5704ca4baa92c217993000d` en scoring/, job_matching_service.py, scoring_config.py, hybrid_search_service.py, atlas_service.py y document_parser.py.
- Build frontend correcto; advertencias históricas de hooks fuera de alcance permanecen congeladas.
- El chequeo global de cierre sigue reportando **9 problemas preexistentes**, ya presentes al comenzar: dos referencias a almacenamiento local de respaldo en rutas de upload, cuatro redefiniciones de modelos, dos incidencias de lint en rutas existentes y una redefinición en taxonomía. No se alteraron esas áreas por la restricción de no reconstruir/cambiar extracción o clasificación sin OK. No afirmar que el chequeo global está limpio; las pruebas específicas de este trabajo sí pasan.

### Pendiente de autorización (P0)
- Segunda pasada con umbral <0,75, campos faltantes o claves inválidas; recuperar extracción antes del modelo, CV completo, industria dominante por meses de última década, títulos/responsabilidades y unión de fechas laborales; caché/deduplicación por versión.
- Búsqueda web disponible para el agente, NO integrada en la aplicación; propuesta solo para empresas desconocidas, sin enviar datos personales del candidato.
- Manejo `Requiere captura manual` y aviso específico de ilegibilidad siguen pendientes de implementación junto con extracción/OCR. El OCR actual sigue fallando en los casos diagnosticados.
- No reprocesar ni aprobar los 34 candidatos sin autorización.
- Continuidad garantizada respecto a pestaña/navegación DESPUÉS de recepción del archivo. No se resolvió la limitación existente de bytes de cola en memoria ante reinicios del servidor.

## Operación anterior — 2026-09-22
**Solicitud:** desactivar a Patricia Sáez (`psaez@humaniq.com.mx`) con `is_active: false`, conservar historial y comprobar login 403.
- Cuenta identificada unívocamente: `bb8ac7a2-ba5b-4312-9baa-f2bbf973f4bc`.
- Aplicado `PUT /api/users/{id}` con únicamente `{"is_active": false}`; respuesta HTTP 200. El servicio también actualiza `updated_at`.
- Lectura posterior confirma que la cuenta existe, está inactiva y no aparece entre usuarios activos. Comparación del documento expuesto por API: solo cambiaron `is_active` y `updated_at`.
- No se modificó código de aplicación ni se restablecieron contraseñas. No se borraron ni reasignaron candidatos, notas o asignaciones.
- `GET /api/auth/me` con JWT de comprobación válido y efímero de la cuenta inactiva: HTTP 403, `Cuenta desactivada`. Token mantenido solo en memoria y con expiración de 60 segundos.
- **Límite de verificación:** `POST /api/auth/login` comprueba la contraseña ANTES del estado activo. La prueba con contraseña aleatoria devolvió HTTP 401. No se dispone de la contraseña real de Patricia; por tanto, NO se verificó un HTTP 403 real de login con contraseña correcta. No afirmar que esa prueba se realizó.
- La comparación literal inicial de respuestas de candidatos varió por ocho `ai_classification.classified_at` generados por el valor por defecto del modelo en cada lectura. Dos GET consecutivos reprodujeron la diferencia; las asignaciones no variaron. No confundir esta diferencia de serialización con una modificación de historial ni afirmar una comparación íntegra antes/después aprobada.
- Evidencia: `test_reports/patricia_deactivation_20260922.json`.

## Documentación e historial
- `CHANGELOG.md`: operaciones recientes y cambios verificados.
- `CHANGELOG_LEGACY.md`: copia íntegra del PRD anterior, conservada al dividir el documento que superaba 700 líneas. Incluye fases, decisiones, arquitectura histórica y referencias de pruebas.
- `ROADMAP.md`: pendientes y tareas congeladas.
- Propuesta de segunda pasada pendiente de OK; solo se autorizaron e implementaron las mejoras descritas de bandeja y seguimiento de carga.