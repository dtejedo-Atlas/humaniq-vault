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

## Último trabajo — 2026-09-22: revisión y seguimiento de carga
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