# Checklist de Validación Operativa - Atlas Talent Vault

## Objetivo
Validar el sistema con casos reales de reclutamiento para detectar errores, inconsistencias y mejoras puntuales antes de entrar a producción.

---

## 1. CARGA DE CVs (Upload)

### Flujo Básico
- [ ] Subir 1 CV individual (PDF)
- [ ] Subir 1 CV individual (DOCX)
- [ ] Subir batch de 5-10 CVs mixtos
- [ ] Verificar que el parsing extrajo correctamente:
  - [ ] Nombre completo
  - [ ] Email y teléfono
  - [ ] Ubicación (ciudad/estado)
  - [ ] Puesto actual y empresa
  - [ ] Experiencia laboral (años)
  - [ ] Idiomas detectados

### Verificar Atlas AI
- [ ] Clasificar candidato recién cargado
- [ ] Revisar clasificación sugerida (industria, área funcional, seniority)
- [ ] Aprobar clasificación y verificar que se aplica al perfil
- [ ] Tags sugeridos son relevantes

### Casos Edge
- [ ] CV con formato inusual (sin estructura clara)
- [ ] CV en inglés
- [ ] CV muy largo (+10 páginas)
- [ ] CV con caracteres especiales (acentos, ñ)

---

## 2. BÚSQUEDA

### Búsqueda Simple
- [ ] Buscar por nombre exacto
- [ ] Buscar por puesto ("CFO", "Director de Finanzas")
- [ ] Buscar por empresa ("FEMSA", "Bimbo")
- [ ] Buscar por industria
- [ ] Buscar por ubicación ("CDMX", "Monterrey")

### Búsqueda Semántica (AI)
- [ ] Buscar concepto: "experiencia en transformación digital"
- [ ] Buscar perfil: "líder comercial con inglés avanzado"
- [ ] Verificar que resultados semánticos son relevantes
- [ ] Comparar resultados con y sin semántica

### Filtros Combinados
- [ ] Industria + Seniority
- [ ] Área funcional + Años de experiencia
- [ ] Múltiples áreas funcionales

---

## 3. SMART FOLDERS

### Verticales de Negocio
- [ ] Abrir "CFO & Finanzas" - verificar candidatos relevantes
- [ ] Abrir "Operaciones" - verificar candidatos relevantes
- [ ] Abrir "Comercial & Ventas" - verificar candidatos relevantes
- [ ] Conteos coinciden con realidad (contar manualmente 5 perfiles)

### Folders de Proceso
- [ ] "Recién Ingresados" muestra CVs nuevos (status: new)
- [ ] "En Evaluación" muestra candidatos en revisión/calificados
- [ ] "Listos para Enviar" muestra candidatos ready_to_send

### Navegación
- [ ] Click en folder navega correctamente
- [ ] Sidebar hace scroll si hay muchos folders
- [ ] Conteos se actualizan al cambiar status de candidatos

---

## 4. PIPELINE DE ESTADOS

### Flujo Normal de Candidato
- [ ] Nuevo → En Revisión (iniciar evaluación)
- [ ] En Revisión → Calificado (perfil validado)
- [ ] Calificado → Listo para Enviar (preparar presentación)
- [ ] Listo para Enviar → Presentado (envió a cliente)
- [ ] Presentado → Entrevistado (cliente lo entrevistó)
- [ ] Entrevistado → Oferta (negociación)
- [ ] Oferta → Colocado (contratado)

### Flujos Alternativos
- [ ] Cualquier status → En Pausa (pausar proceso)
- [ ] Cualquier status → Descartado (rechazar)
- [ ] Descartado → En Revisión (reactivar)
- [ ] En Pausa → En Revisión (reactivar)

### Historial
- [ ] Cada cambio se registra con fecha/hora
- [ ] Se guarda quién hizo el cambio
- [ ] Notas opcionales se guardan correctamente
- [ ] Modal de historial muestra todos los cambios

---

## 5. JOB MATCHING

### Crear Vacante
- [ ] Crear vacante con descripción completa
- [ ] Asignar industria y área funcional
- [ ] Definir seniority requerido
- [ ] Agregar requisitos específicos

### Matching
- [ ] Ejecutar matching en vacante
- [ ] Revisar top 10 candidatos sugeridos
- [ ] Scores de match son coherentes con requisitos
- [ ] Candidatos irrelevantes tienen score bajo

### Shortlist
- [ ] Agregar candidatos a shortlist de vacante
- [ ] Quitar candidatos de shortlist
- [ ] Shortlist persiste entre sesiones

---

## 6. EXPORTACIÓN

### PDF Export
- [ ] Exportar shortlist de vacante en PDF
- [ ] Verificar branding Humaniq
- [ ] Verificar formato ejecutivo (resumen, no CV completo)
- [ ] SIN información de contacto (para no-admin)
- [ ] CON información de contacto (para admin)

### DOCX Export
- [ ] Exportar shortlist en Word
- [ ] Documento es editable
- [ ] Formato consistente con PDF

---

## 7. MULTI-USUARIO

### Roles
- [ ] Admin puede ver/editar todos los candidatos
- [ ] Recruiter puede ver todos pero editar solo asignados
- [ ] Advertencia de "solo lectura" aparece para no-asignados

### Asignaciones
- [ ] Admin asigna candidato a recruiter
- [ ] Recruiter puede editar candidato asignado
- [ ] Admin puede quitar asignación
- [ ] Múltiples recruiters pueden estar asignados

---

## 8. CASOS REALES RECOMENDADOS

### Caso 1: Director de Finanzas para empresa de retail
1. Crear vacante con requisitos específicos
2. Ejecutar matching
3. Evaluar top 5 candidatos
4. Mover 3 a "Calificado"
5. Exportar shortlist PDF

### Caso 2: Gerente de Operaciones para manufactura
1. Buscar "operaciones manufactura director"
2. Filtrar por CDMX/Monterrey
3. Revisar perfiles
4. Asignar a recruiter específico
5. Cambiar estados según avanza proceso

### Caso 3: Carga masiva de base existente
1. Subir 20+ CVs de base actual
2. Verificar parsing de todos
3. Clasificar con Atlas AI
4. Organizar en Smart Folders

---

## 9. MÉTRICAS DE ÉXITO

### Funcionalidad
- [ ] 0 errores críticos que bloqueen flujo
- [ ] Parsing exitoso en >90% de CVs
- [ ] Matching relevante en >80% de casos

### Performance
- [ ] Búsqueda responde en <3 segundos
- [ ] Carga de páginas <2 segundos
- [ ] Upload de CV individual <10 segundos

### Usabilidad
- [ ] Flujo intuitivo sin necesidad de manual
- [ ] Información importante visible sin scroll excesivo
- [ ] Acciones principales accesibles en <3 clicks

---

## 10. REGISTRO DE HALLAZGOS

### Errores Encontrados
| Fecha | Descripción | Severidad | Status |
|-------|-------------|-----------|--------|
|       |             |           |        |

### Mejoras Sugeridas
| Fecha | Descripción | Prioridad | Status |
|-------|-------------|-----------|--------|
|       |             |           |        |

### Inconsistencias
| Fecha | Descripción | Acción |
|-------|-------------|--------|
|       |             |        |

---

## Notas
- Este checklist es para validación pre-producción
- Documentar cada hallazgo con screenshots si es posible
- Priorizar errores que bloquean flujos principales
- Las mejoras pueden acumularse para siguiente fase
