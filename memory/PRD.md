# Atlas Talent Vault - Product Requirements Document

## Descripción General
Sistema de reclutamiento AI para firma de headhunting en México. Permite subir CVs, extraer datos automáticamente, clasificar candidatos con IA, y realizar búsquedas semánticas avanzadas.

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

### Fase 2 (Planificada)
- [ ] Motor de matching candidato-vacante
- [ ] Smart Folders (carpetas dinámicas)
- [ ] Sistema multi-usuario con roles granulares
- [ ] Centro de merge de duplicados

### Fase 3 (Futura)
- [ ] Analytics para admin
- [ ] Exportación de datos
- [ ] Búsquedas guardadas avanzadas

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
├── server.py              # API principal
├── models.py              # Modelos Pydantic
├── taxonomy.py            # Taxonomía maestra bilingüe
├── atlas_service.py       # Servicio de clasificación AI
├── text_utils.py          # Normalización UTF-8
├── error_handling.py      # Sistema de errores detallados (NUEVO)
├── hybrid_search_service.py  # Búsqueda híbrida
└── embedding_service.py   # Generación de embeddings (opcional)

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

---

## Limitaciones Conocidas

1. **Embeddings desactivados temporalmente**: La EMERGENT_LLM_KEY no funciona para OpenAI embeddings directamente. Se requiere una `OPENAI_API_KEY` separada en `.env` para habilitar búsqueda semántica.

2. **Archivos .doc (Word antiguo)**: Requieren conversión manual a PDF o DOCX. El sistema da mensaje claro.

3. **Escalabilidad vectorial**: Búsqueda manual de cosine similarity. Planificado migrar a MongoDB Atlas Vector Search.

---

## Próximos Pasos
1. **🔴 IMPLEMENTAR: Scoring v2.1** - Ver `/app/memory/SCORING_V2_FINAL.md`
   - Modelo aprobado con ajustes del usuario
   - Pesos: Funcional(40%), Seniority(20%), Industria(15%), Semántico(10%), Keywords(8%), Trayectoria(5%), Estabilidad(2%)
   - Threshold mínimo: 45
   - GM penalty condicional basado en evidencia funcional
2. 🟡 Validar con queries reales post-implementación
3. 🔵 Fase 2: Motor de matching candidato-vacante (basado en Scoring v2.1)

## Arquitectura de Búsqueda (Definitiva)

| Ubicación | Endpoint | Motor | Comportamiento |
|-----------|----------|-------|----------------|
| `/search` | POST /api/search/hybrid | hybrid_search_service | Búsqueda avanzada con filtros |
| `/candidates` | GET /api/candidates?search= | hybrid_search_service | Lista con búsqueda integrada |
| Header global | Redirige a /search?q= | N/A | Acceso rápido desde cualquier página |
| `/upload` | N/A | N/A | Solo carga de CVs |
| `/dashboard` | N/A | N/A | Solo estadísticas |
