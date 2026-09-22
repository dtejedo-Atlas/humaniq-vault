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
