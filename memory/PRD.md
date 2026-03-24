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
- [x] **Taxonomía bilingüe con keys canónicas** (implementado 24-Mar-2026)
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
- **Embeddings:** OpenAI text-embedding-3-small
- **Storage:** Emergent Object Storage
- **Auth:** JWT

### Estructura de Archivos Clave
```
/app/backend/
├── server.py           # API principal
├── models.py           # Modelos Pydantic
├── taxonomy.py         # Taxonomía maestra bilingüe
├── atlas_service.py    # Servicio de clasificación AI
├── text_utils.py       # Normalización UTF-8
├── hybrid_search_service.py  # Búsqueda híbrida
└── embedding_service.py      # Generación de embeddings

/app/frontend/src/
├── pages/              # Páginas React
├── components/         # Componentes UI
├── contexts/           # AuthContext, TaxonomyContext
└── api/               # Cliente API
```

---

## Modelo de Datos

### Candidate
```json
{
  "id": "uuid",
  "full_name": "José Muñoz García",
  "full_name_normalized": "jose munoz garcia",  // Para búsqueda
  "email": "jose@example.com",
  "industry": "manufacturing",  // KEY canónica
  "functional_area": "operations",  // KEY canónica
  "seniority": "director",
  "embedding": [0.1, 0.2, ...]  // Vector para búsqueda semántica
}
```

### Industry / FunctionalArea (Taxonomía)
```json
{
  "id": "uuid",
  "key": "manufacturing",       // Identificador canónico
  "name_es": "Manufactura",     // Nombre para UI (español)
  "name_en": "Manufacturing"    // Nombre en inglés
}
```

---

## Changelog

### 24-Mar-2026 - Taxonomía Bilingüe
- Implementado sistema de taxonomía con keys canónicas neutras al idioma
- Campos: `key`, `name_es`, `name_en` para industrias y áreas funcionales
- El AI (Atlas) ahora clasifica CVs en español o inglés hacia la misma key canónica
- Frontend traduce keys a nombres en español para mostrar en UI
- Endpoint `/api/taxonomy/lookup` para mapeo key -> nombres
- Migración ejecutada para actualizar datos existentes

### 24-Mar-2026 - Validación UTF-8
- Confirmado funcionamiento de búsqueda con y sin acentos
- "jose munoz" encuentra "José Muñoz García"
- Campos `*_normalized` usados solo para búsqueda

---

## Testing

### Credenciales de prueba
- Email: test_utf8@atlas.com
- Password: test123456

### Reportes de prueba
- /app/test_reports/iteration_1.json
- /app/test_reports/iteration_2.json
- /app/test_reports/iteration_3.json (taxonomía bilingüe - 100% passed)

---

## Limitaciones Conocidas
1. **Búsqueda vectorial:** Actualmente usa cálculo manual de cosine similarity. Planificado migrar a MongoDB Atlas Vector Search para escalabilidad.

---

## Próximos Pasos
1. Validación controlada con CVs reales (50-100)
2. Ajustes según feedback
3. Iniciar Fase 2 con motor de matching
