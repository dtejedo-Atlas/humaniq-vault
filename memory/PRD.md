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

### Fase 1.5 (Validación) - EN PROGRESO
- [x] Taxonomía bilingüe con keys canónicas (24-Mar-2026)
- [x] Sistema de errores detallados para uploads (24-Mar-2026)
- [ ] Validación controlada con 50-100 CVs reales
- [ ] Ajustes según feedback de validación

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
1. Validación controlada con CVs reales (50-100)
2. Opcional: Agregar OPENAI_API_KEY para embeddings
3. Ajustes según feedback
4. Iniciar Fase 2 con motor de matching
