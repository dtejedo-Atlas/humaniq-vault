# Humaniq Talent Vault - Product Requirements Document

## Descripción General
Sistema de reclutamiento AI para firma de headhunting en México. Permite subir CVs, extraer datos automáticamente, clasificar candidatos con IA, y realizar búsquedas semánticas avanzadas.

**Nombre del sistema:** Humaniq Talent Vault (antes Atlas Talent Vault)

## Stakeholders
- **Usuario Principal:** Reclutadores ejecutivos
- **Mercado:** México y Latinoamérica
- **Idioma por defecto:** Español

---

## Fases del Proyecto

### Fase 1 (MVP) - COMPLETADA
- [x] Autenticación (login/registro)
- [x] Dashboard con estadísticas
- [x] Upload de CVs (PDF/DOCX)
- [x] Parsing con Atlas AI (Claude Sonnet 4.5)
- [x] Clasificación AI (industria, área funcional, seniority)
- [x] Detección de duplicados
- [x] Almacenamiento en Object Storage (Emergent)
- [x] Búsqueda híbrida (filtros + keyword + semántica)
- [x] Embeddings con OpenAI text-embedding-3-small
- [x] Manejo de caracteres UTF-8/acentos
- [x] Framework de validación de calidad

### Fase 1.5 (Validación) - COMPLETADA
- [x] Taxonomía bilingüe con keys canónicas (24-Mar-2026)
- [x] Sistema de errores detallados para uploads (24-Mar-2026)
- [x] Embeddings habilitados con OPENAI_API_KEY (24-Mar-2026)
- [x] Búsqueda semántica operativa - 27/27 candidatos (24-Mar-2026)
- [x] Procesamiento batch paralelo con 3 workers (24-Mar-2026)
- [x] **Calibración de búsqueda híbrida** (24-Mar-2026)
  - Threshold semántico: 30%
  - Score mínimo: 35%
  - Boost keyword+semántica: +20
- [x] **Unificación completa de búsqueda** (24-Mar-2026)
  - GET /api/candidates y POST /api/search/hybrid usan el mismo motor
  - match_score y match_breakdown incluidos en modelo Candidate
  - Header global redirige a /search?q= al presionar Enter
  - SearchPage ejecuta búsqueda automática desde URL params
  - Validado con 6 queries de prueba: 100% consistencia

### Fase 2 (Operacional) - COMPLETADA ✅
- [x] **Job Matching Engine v1** (25-Mar-2026)
  - Motor de matching candidato-vacante completo
  - Scoring: Funcional 35%, Seniority 20%, Industria 15%, Skills 12%, Experiencia 8%, Semántico 5%, Trayectoria 5%
  - Frontend: /jobs (lista) y /jobs/{id} (detalle con ranking)
- [x] **Multi-usuario y Roles** (26-Mar-2026)
  - Roles: super_admin, admin, recruiter, researcher
  - Backend: user_service.py, assignment_service.py
  - Endpoints: /api/users, /api/users/me, /api/users/recruiters
  - Frontend: /users (gestión de equipo, solo Admin)
- [x] **Asignación de Candidatos** (26-Mar-2026)
  - Regla: Recruiters ven toda la BD pero solo editan candidatos asignados
  - Endpoints: /api/candidates/{id}/assign, /api/candidates/{id}/can-edit
  - UI: Banner "Modo solo lectura" para recruiters sin asignación
  - Sección "Asignaciones" en perfil de candidato
- [x] **Exportación PDF/DOCX Premium** (26-Mar-2026)
  - Backend: export_service.py con WeasyPrint + python-docx
  - Template HTML profesional con branding Humaniq
  - Cover page: vacante, cliente, fecha, preparado por
  - Por candidato: nombre, match%, resumen, fortalezas, riesgos, experiencia, skills
  - Permisos: Admin puede incluir contacto, Recruiter no
  - Trazabilidad: registro en BD de cada exportación
  - Endpoints: POST /api/exports/job/{id}, GET /api/exports/{id}/download
  - Frontend: Dialog de exportación en JobDetailPage
- [x] **Smart Folders** (27-Mar-2026)
  - Backend: smart_folder_service.py con criterios dinámicos
  - 13 folders predefinidos: 9 verticales + 4 de proceso
  - Verticales: CFO, Operaciones, Comercial, Marketing, RRHH, IT, Legal, Supply Chain, General Management
  - Proceso: Listos para Enviar, Top Activos, En Evaluación, Recién Ingresados
  - Sidebar transformado como navegador central de folders
  - Vista de candidatos por folder con selección y exportación
  - Metadata de uso: vistas, exportaciones
  - Endpoints: /api/folders, /api/folders/{id}/candidates
- [x] **Pipeline de Estados de Candidatos** (27-Mar-2026)
  - 10 estados: new, reviewing, qualified, ready_to_send, submitted, interviewed, offer, placed, rejected, on_hold
  - Transiciones validadas (no cualquier estado a cualquier otro)
  - Historial de cambios con timestamp, usuario, y notas
  - Dropdown interactivo en CandidateDetailPage
  - Modal de historial de estados
  - Smart Folders de PROCESO se actualizan automáticamente
  - Endpoints: PUT /api/candidates/{id}/status, GET /api/candidates/{id}/status-history, GET /api/status-config
  - Testing: 12/12 tests passed (iteration_7.json)
  - Bug fix: Sidebar overflow corregido con flex-shrink-0 y min-h-0

### Fase 2.5 (Correcciones Operativas) - COMPLETADA ✅ (27-Mar-2026)
- [x] **Clasificación HR Corregida**
  - Smart Folder "Recursos Humanos" ahora incluye: human_resources, talent_acquisition, hr
  - Corregido mapeo de functional_area en otros folders (IT, Supply Chain, Operations)
  - Endpoint POST /api/folders/initialize?force_update=true para actualizar criterios
- [x] **Soft Delete de Candidatos**
  - Endpoint DELETE /api/candidates/{id} marca is_deleted=true
  - Candidato desaparece de operación pero permanece en BD para trazabilidad
  - Endpoint POST /api/candidates/{id}/restore (solo Admin) para recuperar
  - Todas las queries excluyen automáticamente candidatos eliminados
- [x] **Detección de Duplicados por Niveles**
  - Alta confianza (>=90%): Email exacto → duplicado casi seguro
  - Media confianza (70-90%): Teléfono o LinkedIn similares
  - Baja confianza (<70%): Nombre similar → solo alerta
  - Endpoint GET /api/candidates/{id}/duplicates retorna duplicados categorizados
  - Endpoint POST /api/candidates/merge para fusionar duplicados (solo Admin)
- [x] **Registro Restringido (Lista Negra)**
  - Botón "Marcar como Restringido" en perfil de candidato
  - Categorías: ethical_issue, bad_reference, legal_issue, conflict_of_interest, performance_issue, other
  - Trazabilidad completa: quién, cuándo, motivo, categoría
  - No es bloqueo automático, solo marca para revisión
  - Endpoint POST /api/candidates/{id}/restrict
  - Endpoint POST /api/candidates/{id}/unrestrict (solo Admin)
- [x] **UI de Alertas**
  - Banner rojo para candidatos restringidos con info completa
  - Banner ámbar para duplicados detectados con botón "Ver"
  - Diálogos de confirmación para eliminar y restringir
- [x] **Testing**: iteration_8.json - 21/21 backend tests, 100% frontend verified

### Fase 2.5 (Backlog Operativo) - NO INICIADA
- [ ] Panel "Mis Candidatos" en Dashboard
- [ ] Activity Feed (trazabilidad de acciones)

### Fase 3 (Mejoras Operativas) - EN PROGRESO ✅
#### Fase A (Completada - 13-Abr-2026)
- [x] **Descarga de CV Original** - Botón en perfil de candidato
- [x] **Métricas de Vacantes en Dashboard** - Alertas de vacantes sin candidatos
- [x] **Mejora de Seniority** - Nuevos niveles Trainee/Junior, lógica Título vs Años

#### Subfase B.0 (Completada - 13-Abr-2026)
- [x] **Taxonomía Actualizada**
  - Agregada industria: `fintech` (Fintech / Tecnología Financiera)
  - Actualizado: `real_estate` ahora incluye "Desarrollo Inmobiliario"
  - Sistema de aliases para clasificación AI mejorada
  - Total: 23 industrias, 24 áreas funcionales

#### Fase B.1 (Completada - 13-Abr-2026)
- [x] **Rediseño del Formulario de Vacantes (Wizard)**
  - Formulario wizard de 4 pasos con preview
  - Paso 1: Información básica (título, empresa, área, industria, seniority, experiencia)
  - Paso 2: Contexto y responsabilidades (objetivo, contexto, responsabilidades)
  - Paso 3: Requisitos y ubicación (experiencia requerida, no negociables, ubicación, salario, esquema laboral)
  - Paso 4: Preview final antes de guardar
  - Nuevos campos: `job_objective`, `role_context`, `responsibilities`, `required_experience`, `non_negotiables`, `salary_min`, `salary_max`, `work_scheme`, `schedule`
  - Ubicación estructurada: País + Estado (dropdown para México) + Ciudad
  - Esquema laboral: Presencial / Híbrido / Remoto
  - Tooltips explicativos en cada campo
  - Logo oficial de Humaniq integrado

#### Fase B.2 (Completada - 13-Abr-2026)
- [x] **Ingesta Inteligente de Vacantes**
  - Endpoint `POST /api/jobs/parse-jd` para procesar documentos
  - Soporte para PDF y DOCX
  - Parsing con Claude AI (claude-sonnet-4-5)
  - Extracción automática de: título, empresa, industria, área funcional, seniority, experiencia, ubicación, salario, esquema laboral, responsabilidades, requisitos
  - Validación y normalización de taxonomía
  - Score de confianza y notas de extracción
  - UI integrada en JobFormWizard con zona de upload
  - Preview editable antes de guardar

#### Fase C (Pendiente)
- [ ] **Publicación Externa de Vacantes** - URLs públicas con branding Humaniq
- [ ] **Tracking de Origen de Candidatos** - Parámetros de fuente en aplicaciones

### Sistema de Gestión de Duplicados (Completado - 13-Abr-2026)
#### Fase 1 - Crítica (COMPLETADO)
- [x] **Detección Mejorada de Duplicados V2**
  - L1 (email idéntico): Bloqueo duro, ofrece actualizar CV existente
  - L2 (linkedin idéntico): Bloqueo duro
  - L3-L5 (teléfono+nombre, nombre+empresas): Sugerencias para revisión
  - Normalización avanzada (case-insensitive, acentos, espacios)
- [x] **Panel de Revisión de Duplicados** (`/duplicates`)
  - Vista de grupos duplicados con estadísticas
  - Comparación lado a lado de candidatos
  - Score de completitud para decidir registro principal
- [x] **Sistema de Merge Manual**
  - Selección de registro principal
  - Opciones granulares: experiencia, educación, skills, notas, CVs
  - Consolidación automática de datos
  - Auditoría completa (quién, cuándo, qué cambios)
  - El registro secundario queda marcado como merged (soft delete)
- [x] **Endpoint Update-CV** para duplicados bloqueados
  - Permite actualizar CV de candidato existente en lugar de crear duplicado

#### Fase 2 - Versionado (COMPLETADO - 14-Abr-2026)
- [x] Modelo `CVVersion` con snapshot completo del parsing
- [x] Servicio `CVVersionService` con CRUD y comparación
- [x] Migración de 108 CVs existentes a `cv_versions`
- [x] Endpoints completos:
  - `GET /candidates/{id}/cv-versions` - Listar versiones
  - `GET /candidates/{id}/cv-versions/{v}` - Detalle de versión
  - `GET /candidates/{id}/cv-versions/{v}/download` - Descargar
  - `GET /candidates/{id}/cv-versions/{v1}/compare/{v2}` - Comparar
  - `POST /candidates/{id}/update-cv` - Subir nueva versión
- [x] UI `CVVersionHistory` integrada en perfil de candidato
  - Lista de versiones con metadata
  - Botón "Nueva versión" para actualizar CV
  - Comparación side-by-side de versiones
  - Descarga por versión
- [x] Flujo de upload actualizado para crear versión con snapshot
- [x] Auditoría completa (quién, cuándo, origen)

#### Fase 3 - Alertas (PENDIENTE)
- [ ] Comparador de versiones con diff
- [ ] Alertas por diferencias significativas
- [ ] Panel de cambios recientes

### Fase 4 (Futura)
- [ ] Registro de Candidatos Restringidos (compliance/ética)
- [ ] Búsqueda booleana avanzada
- [ ] Analytics para admin
- [ ] Exportación de datos
- [ ] Búsquedas guardadas avanzadas
- [ ] Idioma y Ubicación como soft match en Job Matching

---

## Arquitectura Técnica

### Stack
- **Frontend:** React + Shadcn/UI + TailwindCSS
- **Backend:** FastAPI (Python)
- **Base de datos:** MongoDB
- **AI Classification:** Claude Sonnet 4.5 (Emergent LLM Key)
- **Embeddings:** OpenAI text-embedding-3-small (requiere OPENAI_API_KEY)
- **Storage:** Emergent Object Storage
- **Auth:** JWT

### Estructura de Archivos Clave
```
/app/backend/
├── server.py              # API principal (~2700 líneas - deuda técnica)
├── models.py              # Modelos Pydantic (User, Job, Assignment, Export, etc.)
├── user_service.py        # Gestión de usuarios y permisos
├── assignment_service.py  # Asignación de candidatos a recruiters
├── export_service.py      # Generación de PDFs y DOCX
├── job_matching_service.py # Motor de matching vacante-candidato
├── hybrid_search_service.py  # Búsqueda híbrida v2.1
├── scoring_config.py      # Configuración de pesos de scoring
├── affinity_matrices.py   # Matrices de afinidad funcional/industrial
├── taxonomy.py            # Taxonomía maestra bilingüe
├── atlas_service.py       # Servicio de clasificación AI
├── text_utils.py          # Normalización UTF-8
├── embedding_service.py   # Generación de embeddings
└── templates/             # Templates HTML para PDFs
    └── shortlist_report.html

/app/frontend/src/
├── pages/                 # Páginas React
├── components/            # Componentes UI
├── contexts/              # AuthContext, TaxonomyContext
└── api/                   # Cliente API
```

---

## Sistema de Errores (Nuevo)

### Etapas de Procesamiento
1. `upload` - Validación de archivo
2. `storage` - Almacenamiento
3. `text_extraction` - Extracción de texto
4. `ai_parsing` - Parsing con IA
5. `ai_classification` - Clasificación IA
6. `embedding_generation` - Búsqueda semántica
7. `duplicate_detection` - Detección duplicados
8. `database_save` - Guardado en DB
9. `completed` - Completado

### Tipos de Error
| Código | Mensaje Usuario | Recuperable |
|--------|-----------------|-------------|
| `unsupported_format` | Formato no soportado (solo PDF, DOCX) | No |
| `file_corrupted` | Archivo corrupto o dañado | No |
| `file_empty` | Archivo vacío | No |
| `pdf_scanned_no_ocr` | PDF escaneado sin texto | Sí |
| `ai_parsing_failed` | IA no pudo extraer información | Sí |
| `embedding_api_error` | Error generando embeddings | Sí |
| `validation_error` | Datos incompletos del CV | Sí |

### Estados de Respuesta
- `success` - Todo bien
- `partial_success` - Guardado con advertencias
- `failed` - Error crítico
- `duplicate_detected` - Posible duplicado

---

## Changelog

### 25-Mar-2026 - Job Matching Engine v1 Implementado
- **Backend completo:**
  - Modelo Job con campos estructurados (título, industria, área, seniority, skills, etc.)
  - Endpoints CRUD: POST/GET/PUT/DELETE /api/jobs
  - Endpoint de matching: POST /api/jobs/{id}/match
  - Servicio `job_matching_service.py` con scoring adaptado
- **Frontend:**
  - Página /jobs con lista de vacantes y modal de creación
  - Página /jobs/{id} con detalle y candidatos rankeados
  - Breakdown visual de compatibilidad expandible
  - Indicadores de fortalezas, riesgos y skills faltantes
- **Scoring de matching:**
  - Funcional: 35%, Seniority: 20%, Industria: 15%
  - Skills: 12%, Experiencia: 8%, Semántico: 5%, Trayectoria: 5%
- **Validación:** Vacante "Gerente de Operaciones" → María Elena García (86% Match) ✅

### 25-Mar-2026 - Scoring v2.1 Implementado
- **Nuevo sistema de scoring multi-dimensional:**
  - Área Funcional: 40% (mayor peso a función correcta)
  - Seniority: 20% (por distancia de nivel)
  - Industria: 15% (con transferibilidad)
  - Semántico: 13% (inteligencia contextual)
  - Trayectoria: 5% (progresión y consistencia)
  - Keywords: 5% (match textual)
  - Estabilidad: 2% (análisis de rotación)
- **Sistema de penalties:**
  - GM sin evidencia funcional: -25
  - GM con evidencia débil: -20
  - Distancia seniority 4+ niveles: -8 a -15
  - Función adyacente: -8
- **Archivos nuevos:**
  - `scoring_config.py` - Configuración centralizada
  - `affinity_matrices.py` - Matrices de afinidad funcional/industrial
  - `query_parser.py` - Parser de queries
  - `trajectory_analyzer.py` - Análisis de trayectoria y estabilidad
- **Threshold mínimo subido a 45** (más selectivo)
- Validación: HR Executive (82) >> CEO (-7) ✅

### 24-Mar-2026 - Unificación de Búsqueda
- **Arquitectura final de búsqueda:**
  - `/search` → POST /api/search/hybrid → hybrid_search_service ✅
  - `/candidates` → GET /api/candidates?search= → hybrid_search_service ✅
  - Header global → Redirige a /search?q= → SearchPage ejecuta automáticamente ✅
  - `/upload` → Solo carga de CVs (sin búsqueda) ✅
  - `/dashboard` → Solo estadísticas (sin búsqueda) ✅
- Modelo `Candidate` extendido con `match_score: Optional[int]` y `match_breakdown: Optional[Dict]`
- SearchPage ahora lee parámetro `q` de URL y ejecuta búsqueda automáticamente
- Header.js conectado con redirección a /search?q= al presionar Enter
- Validación completa con 6 queries de prueba: 100% consistencia

### 24-Mar-2026 - Sistema de Errores Detallados
- Creado `/app/backend/error_handling.py` con sistema completo de errores
- Cada upload retorna: `status`, `stage_reached`, `errors[]`, `warnings[]`, `processing_time_ms`
- Frontend actualizado para mostrar errores de forma clara y visual
- Soporte mejorado para archivos .doc (Word 97-2003) con mensaje claro
- Endpoint `/api/candidates/retry-processing/{id}` para reintentar procesamiento

### 24-Mar-2026 - Taxonomía Bilingüe
- Implementado sistema de taxonomía con keys canónicas neutras al idioma
- Campos: `key`, `name_es`, `name_en` para industrias y áreas funcionales

### 26-Mar-2026 - Exportación PDF/DOCX Premium
- **Sistema de exportación profesional:**
  - Backend: `export_service.py` con WeasyPrint (PDF) + python-docx (DOCX)
  - Template HTML con branding Humaniq (elegante, consultoría ejecutiva)
  - Cover page: título de vacante, cliente, fecha, preparado por
  - Por candidato: nombre, match%, resumen ejecutivo, fortalezas, riesgos, experiencia, skills
- **Permisos y trazabilidad:**
  - Admin/Super Admin: pueden incluir info de contacto
  - Recruiter: puede exportar pero SIN contacto (sistema ignora el flag)
  - Registro en BD: user_id, candidate_ids, included_contact_info, timestamp
- **Endpoints:**
  - POST /api/exports/job/{id} - Exportar shortlist de vacante
  - POST /api/exports/candidates - Exportar selección custom
  - GET /api/exports/{id}/download - Descargar archivo
  - GET /api/exports - Listar exportaciones
- **Frontend:**
  - Botón "Exportar Shortlist" en JobDetailPage
  - Dialog con opciones: formato (PDF/DOCX), límite (5-20), cliente, riesgos, contacto
  - Descarga automática al completar
- **Archivos:**
  - `/app/backend/export_service.py`
  - `/app/backend/templates/shortlist_report.html`
  - Exports guardados en `/app/backend/exports/`

### 26-Mar-2026 - Multi-usuario y Asignaciones
- **Backend completado:**
  - `user_service.py`: Gestión de usuarios con verificación de permisos
  - `assignment_service.py`: Asignación de candidatos a recruiters
  - Endpoints: GET/POST /api/users, GET /api/users/me, GET /api/users/recruiters
  - Endpoints: POST /api/candidates/{id}/assign, DELETE /api/candidates/{id}/assign/{recruiter_id}
  - Endpoint: GET /api/candidates/{id}/can-edit (verifica permisos de edición)
- **Frontend completado:**
  - `/users` (UsersPage.js): Tabla de usuarios con roles, estadísticas, acciones de editar/desactivar
  - Modal de creación de usuarios con selector de rol
  - Candidate Detail: Sección "Asignaciones" visible para todos
  - Banner "Modo solo lectura" para recruiters sin asignación
  - Botón Editar deshabilitado cuando no tiene permisos
  - Botón Asignar solo visible para Admin
- **Reglas de negocio implementadas:**
  - Admin/Super Admin: Pueden ver y editar todo
  - Recruiter: Puede ver toda la BD pero solo editar candidatos asignados
  - Página /users: Solo accesible para Admin
  - UI muestra restricción claramente, no parece bug
- **Testing:** 17/17 tests backend pasando, UI verificada

---

## Limitaciones Conocidas

1. **Embeddings desactivados temporalmente**: La EMERGENT_LLM_KEY no funciona para OpenAI embeddings directamente. Se requiere una `OPENAI_API_KEY` separada en `.env` para habilitar búsqueda semántica.

2. **Archivos .doc (Word antiguo)**: Requieren conversión manual a PDF o DOCX. El sistema da mensaje claro.

3. **Escalabilidad vectorial**: Búsqueda manual de cosine similarity. Planificado migrar a MongoDB Atlas Vector Search.

---

## Estabilización Pre-Deploy (14-Abr-2026) ✅

### Checklist Completado:
1. ✅ **Bug de Merge corregido** - TypeError en `duplicate_detector_v2.py` al ordenar experiencias con fechas `None`
2. ✅ **Duplicados fusionados** - 7 merges exitosos, 0 duplicados activos restantes
3. ✅ **CV Versioning E2E** - Upload, historial, comparación y descarga funcionando
4. ✅ **Sistema E2E** - Upload → Search → Smart Folders → Status → Matching → Export → Download CV
5. ✅ **Permisos validados en API** - Recruiters solo pueden editar candidatos asignados (backend + frontend)
6. ✅ **Backup documentado** - mongodump para colecciones críticas

### Bugs Corregidos:
- `duplicate_detector_v2.py` línea 399: `x.get('start_date', '')` → `x.get('start_date') or ''`
- `server.py` línea 2530: `storage_service.download_file()` → `storage_service.get_object()`
- `server.py` línea 956: `candidate.location` → `candidate.city/state` (modelo actualizado)
- `server.py` línea 3614: `db.candidate_assignments` → `db.assignments` (colección correcta)
- `duplicate_detector_v2.py` línea 500: `db.candidate_assignments` → `db.assignments`

### Validación de Permisos API (14-Abr-2026):
| Endpoint | Admin | Recruiter (asignado) | Recruiter (no asignado) |
|----------|-------|---------------------|------------------------|
| PUT /candidates/{id} | ✅ | ✅ | ❌ Bloqueado |
| POST /candidates/{id}/notes | ✅ | ✅ | ❌ Bloqueado |
| PUT /candidates/{id}/status | ✅ | ✅ | ❌ Bloqueado |
| POST /candidates/{id}/restrict | ✅ | ✅ | ❌ Bloqueado |
| POST /candidates/{id}/update-cv | ✅ | ✅ | ❌ Bloqueado |
| POST /candidates/{id}/reclassify-seniority | ✅ | ✅ | ❌ Bloqueado |

### Estado de la Base de Datos:
- 31 candidatos activos
- 7 registros merged (soft deleted)
- 109 versiones de CV
- 10 usuarios
- 5 vacantes
- 0 duplicados pendientes

## Próximos Pasos
1. 🟢 **COMPLETADO: Estabilización Pre-Deploy** (14-Abr-2026)
2. 🟡 **Panel "Mis Candidatos"** - Vista rápida de asignaciones en Dashboard
3. 🔵 **Activity Feed** - Trazabilidad de acciones del sistema
4. 🔵 **Fase 3: Alertas por Diferencias** - Notificaciones de cambios significativos en CVs
5. 🔵 **Fase C: Publicación Externa** - URLs públicas de vacantes

## Deuda Técnica
- `server.py` tiene ~4200 líneas. Planificar división en routers modulares
- PUT `/api/candidates/{id}` no valida permisos de asignación (UI sí lo hace)

## Correcciones Recientes (30-Jun-2026)

### Fix: Redistribución Dinámica de Pesos en Búsqueda Híbrida
- **Problema:** Al buscar un skill puro (ej: "Java", "SAP", "BI"), el sistema ignoraba el keyword porque pesaba solo 5%, mientras que área funcional (40%), seniority (20%) e industria (15%) devolvían scores neutrales para todos los candidatos. Resultado: rankings irrelevantes.
- **Solución implementada:**
  - `hybrid_search_service.py` v2.2: Nuevo método `_calculate_dynamic_weights()` redistribuye pesos según dimensiones presentes en la query.
  - Si query tiene solo keywords → keywords=65%, semántico=13%, trayectoria=10%
  - Si query tiene área + keywords → keywords=33% (redistribución parcial)
  - Si query es completa (área+seniority+industria) → pesos estándar sin cambios
- **Archivos modificados:**
  - `/app/backend/hybrid_search_service.py` - v2.2 con pesos dinámicos
  - `/app/backend/query_parser.py` - v2.1 con whitelist de skills cortos
- **Tests:** 16/16 passed (`/app/backend/tests/test_dynamic_weights.py`)

### Fix: Soporte para Skills Cortos (BI, AI, ML, Go, R, C#)
- **Problema:** `extract_keywords()` filtraba palabras < 3 caracteres, descartando skills válidos como "BI", "AI", "ML", "Go", "R".
- **Solución:**
  - `query_parser.py` ahora tiene `SHORT_SKILLS_WHITELIST` con 30+ skills cortos válidos
  - `SPECIAL_CHAR_SKILLS` para tokens como "C#", "C++", "F#", ".NET"
  - `extract_keywords()` acepta tokens de 2+ chars si están en la whitelist

### Fix: CVs Multi-Columna y Validación Resiliente de Upload (30-Jun-2026)
- **Problema:** CVs con diseño de dos columnas (Canva, plantillas) fallaban con "Error procesando CV". Error real: `'Candidate' object has no attribute 'education'`.
- **Solución implementada:**
  1. **Extracción Multi-Columna** (`document_parser.py` v2.1):
     - Nuevo método `_detect_columns()` detecta layout multi-columna basado en coordenadas x
     - Nuevo método `_extract_text_multi_column()` extrae texto respetando columnas
     - CVs de Canva ahora se extraen en orden lógico (columna izquierda → columna derecha)
  2. **Validación Resiliente** (`server.py`):
     - Nuevas funciones helper: `safe_int()`, `safe_string()`, `safe_list()`, `clean_previous_companies()`
     - `years_experience` como "10 años" o "5+" se convierte a int correctamente
     - `previous_companies` con campos faltantes o alternativos se limpia sin fallar
     - Aplicado tanto al endpoint sync (`upload-resume`) como al path batch (`process_cv_job`)
  3. **Removida referencia a `candidate.education`** que no existe en el modelo
- **Tests:** 20/20 passed (`/app/backend/tests/test_cv_upload_resilience.py`)

## Arquitectura de Búsqueda (Definitiva)

| Ubicación | Endpoint | Motor | Comportamiento |
|-----------|----------|-------|----------------|
| `/search` | POST /api/search/hybrid | hybrid_search_service | Búsqueda avanzada con filtros |
| `/candidates` | GET /api/candidates?search= | hybrid_search_service | Lista con búsqueda integrada |
| Header global | Redirige a /search?q= | N/A | Acceso rápido desde cualquier página |
| `/upload` | N/A | N/A | Solo carga de CVs |
| `/dashboard` | N/A | N/A | Solo estadísticas |

### Fix: Fusión de N Duplicados y Limpieza de Huérfanos (30-Jun-2026)
- **Problema:** El flujo de merge solo soportaba 2 candidatos. Con grupos de 3+ duplicados, el botón "Fusionar candidato" no funcionaba.
- **Solución implementada:**
  1. **Backend - Endpoint merge-multiple** (`server.py`):
     - Nuevo endpoint `POST /api/candidates/merge-multiple` que acepta `primary_candidate_id` y lista de `secondary_candidate_ids`
     - Fusiona secuencialmente todos los secundarios en el principal
     - Validación: verifica que el primary exista antes de proceder
  2. **Backend - Limpieza de huérfanos** (`server.py`):
     - `GET /api/duplicates/orphan-records`: Identifica registros incompletos (sin email, sin CV, nombre genérico)
     - `POST /api/duplicates/cleanup-orphans`: Soft delete de registros seleccionados
     - Solo admins pueden ejecutar limpieza
  3. **Frontend - DuplicatesPage.js** completamente reescrito:
     - Soporta selección de candidato principal entre N opciones
     - Muestra badge visual "Principal" vs "Se fusionará" para cada candidato
     - Diálogo de huérfanos con categorización y selección múltiple
     - Feedback de errores con toast descriptivo
- **Resultado:** Los 4 candidatos "Alex Shapiro" fueron fusionados exitosamente en uno solo
- **Tests:** 13/14 passed (`/app/backend/tests/test_duplicates_merge_multiple.py`)

### Mejora: CVVersionHistory más visible (30-Jun-2026)
- **Objetivo:** Mejorar visibilidad del historial de CVs en el perfil del candidato.
- **Cambios implementados:**
  1. **Diseño destacado** (`CVVersionHistory.js`):
     - Header con gradiente cyan-600 → blue-600 y texto blanco
     - Wrapper con fondo degradado cyan-50 → blue-50 en CandidateDetailPage
     - Ícono de historial en recuadro semitransparente
     - Contador de versiones visible sin expandir
  2. **Versiones individuales mejoradas:**
     - Card con borde cyan para versión actual, badge "Actual" destacado
     - Fecha usa `uploaded_at || created_at` correctamente
     - Botón "Descargar" cyan sólido (en lugar de ghost)
     - data-testid para cada versión y botón descarga
  3. **UX mejorada:**
     - Estado vacío claro con ícono e instrucciones
     - Notas de versión con fondo destacado
- **Fix:** Corregida pluralización española ("versiónes" → "versiones")
- **Tests:** Frontend 100% validated (UI structure, expand/collapse, empty state, upload dialog)

### Code Quality: Hardcoded Secrets Removed (30-Jun-2026)
- **Item 1 completado:** Credenciales de tests movidas a `os.getenv()` con defaults
- **Archivos actualizados:**
  - `tests/test_cv_upload_resilience.py`
  - `tests/test_duplicates_merge_multiple.py`
  - `tests/test_dynamic_weights.py`
  - `tests/test_operational_fixes.py`
  - `tests/test_scoring_v21.py`
  - `tests/test_search_unification.py`
  - `tests/test_status_pipeline.py`
  - `tests/test_taxonomy_and_search.py`
  - `tests/test_users_assignments.py`
- **Variables de entorno añadidas:**
  - `TEST_ADMIN_EMAIL` (default: `test_utf8@atlas.com`)
  - `TEST_ADMIN_PASSWORD` (default: `Humaniq123`)
  - `TEST_RECRUITER_EMAIL` (default: `recruiter_test@atlas.com`)
  - `TEST_RECRUITER_PASSWORD` (default: `Humaniq123`)
- **Item 2 (is vs ==):** Revisado - no se encontraron instancias de `is` con literales que necesiten cambio. Los `== True` existentes son necesarios para distinguir `True` de `None`.
- **Tests:** 135 passed, 7 failed (fallos preexistentes por datos desactualizados), 1 skipped


### Feature: Bandeja de Clasificaciones Por Revisar (30-Jun-2026)
- **Objetivo:** Permitir a reclutadores revisar y aprobar/corregir clasificaciones de IA con baja confianza o candidatos sin clasificar.
- **Backend implementado:**
  1. **GET /api/atlas/classifications/pending** - Lista candidatos pendientes de revisión:
     - Incluye candidatos con `ai_classification.confidence_score < 0.75`
     - Incluye candidatos con `ai_classification = null` (sin clasificar)
     - Ordenados por confidence_score ascendente (más baja primero)
     - Paginación con skip/limit
  2. **GET /api/atlas/classifications/pending/count** - Contador para badge en sidebar
  3. **POST /api/atlas/classifications/bulk-approve** - Aprobación masiva:
     - Maneja candidatos CON clasificación (aplica valores AI)
     - Maneja candidatos SIN clasificación (crea registro manual)
  4. **POST /api/atlas/classifications/correct/{id}** - Corrección manual:
     - Acepta `industry`, `functional_area`, `seniority`
     - Reconstruye `ai_classification` completo (evita dot-notation en null)
     - Marca `was_corrected: true`
  5. **POST /api/atlas/approve-classification/{id}** - Aprobación individual:
     - Actualizado para manejar `ai_classification = null`
- **Frontend implementado:**
  1. **ClassificationReviewPage.js** - Nueva página:
     - Stats: pendientes, umbral 75%, seleccionados
     - Lista de candidatos con checkbox para selección múltiple
     - Botones "Aprobar" y "Corregir" por candidato
     - Diálogo de corrección con dropdowns de taxonomía
     - Botón bulk "Aprobar N seleccionados"
  2. **TaxonomyContext.js** - Actualizado:
     - Añadido `seniorityLevels` cargado desde `/api/taxonomy/seniority-levels`
     - Nuevos helpers: `getSeniorityName()`, `getSeniorityOptions()`
  3. **Sidebar.js** - Badge con count de pendientes
  4. **App.js** - Ruta `/review` → `ClassificationReviewPage`
- **Bugs corregidos:**
  1. P0 Frontend crash: `seniorityLevels.find()` causaba TypeError porque el contexto no lo exponía
  2. P1 Backend exclusión: Pipeline usaba `$ifNull` con default=1, excluyendo candidatos sin clasificar
  3. P0 Approve crash: Endpoint rechazaba candidatos sin `ai_classification`
  4. P0 Correct crash: Dot-notation en MongoDB fallaba cuando `ai_classification = null`
- **Tests:** Backend 11/11 pytest pass, Frontend funcional con dropdowns vacíos (issue menor de timing)
- **Candidatos sin functional_area:** Los 6 candidatos reportados ahora aparecen en la bandeja con 0% confianza

---

## Tareas Congeladas (por instrucción del usuario - 30-Jun-2026)
Las siguientes tareas están **PAUSADAS** hasta nueva instrucción:
- Code Quality Items 3-9 (React hooks, localStorage, massive components, etc.)
- Panel "Mis Candidatos" 
- Activity Feed
- Alertas por diferencias en CVs
- Refactorización de `server.py` (>4800 líneas)
- Publicación Externa de Vacantes
- Tracking de Origen de Candidatos
