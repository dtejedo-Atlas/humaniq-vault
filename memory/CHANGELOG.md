# CHANGELOG - Humaniq Talent Vault

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
