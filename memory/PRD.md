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

## Próximos Pasos
1. **🟢 COMPLETADO: Multi-usuario y Asignaciones** (26-Mar-2026)
2. **🟢 COMPLETADO: Exportación PDF/DOCX Premium** (26-Mar-2026)
3. **🟢 COMPLETADO: Smart Folders** (27-Mar-2026)
4. 🟡 **Panel "Mis Candidatos"** - Vista rápida de asignaciones en Dashboard
5. 🔵 **Activity Feed** - Trazabilidad de acciones del sistema
6. 🔵 **Registro de Candidatos Restringidos** - Sistema de compliance/ética (arquitectura base)
7. 🔵 **Idioma y Ubicación en Job Matching** - Soft matching adicional

## Deuda Técnica
- `server.py` tiene ~2900 líneas. Planificar división en routers modulares (/routers/jobs.py, /routers/users.py, /routers/exports.py, /routers/folders.py, etc.)

## Arquitectura de Búsqueda (Definitiva)

| Ubicación | Endpoint | Motor | Comportamiento |
|-----------|----------|-------|----------------|
| `/search` | POST /api/search/hybrid | hybrid_search_service | Búsqueda avanzada con filtros |
| `/candidates` | GET /api/candidates?search= | hybrid_search_service | Lista con búsqueda integrada |
| Header global | Redirige a /search?q= | N/A | Acceso rápido desde cualquier página |
| `/upload` | N/A | N/A | Solo carga de CVs |
| `/dashboard` | N/A | N/A | Solo estadísticas |
