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

## Última operación — 2026-09-22
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
- No hay nuevas funcionalidades propuestas o autorizadas en esta operación.