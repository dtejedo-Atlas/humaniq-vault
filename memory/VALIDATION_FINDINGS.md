# Atlas Talent Vault - Hallazgos de Validación

## Fecha: 24-Mar-2026 (Actualizado: 25-Mar-2026)

---

## Ronda de Validación Completa

### Hallazgos Detallados

| Query | Resultados | Problema |
|-------|------------|----------|
| `HR Manager manufactura` | 2 CEOs + 1 COO | Perfiles de dirección general en vez de HR |
| `Finance Manager retail` | 0 resultados | Posible falso negativo |
| `Operations Manager industrial` | COO + Director General | Mezclados con experiencia operativa |
| `Supply Chain Manager consumo` | 1 COO correcto + 1 CEO/DG sin SC | Mezcla correcto con incorrecto |
| `Marketing Manager B2B` | 2 marketing + 2 ventas | Aceptable pero ventas rankea muy alto |

### Conclusiones Clave

1. **Sobreponderación de seniority alto** - CEOs/DGs aparecen en búsquedas funcionales específicas
2. **Falta peso a área funcional principal** - General management rankea sobre especialistas
3. **Mezcla de funciones cercanas** - Marketing/Ventas se confunden (parcialmente aceptable)
4. **Industria y área funcional deben pesar más que jerarquía general**

---

## Hallazgo Original: Falso Positivo en Búsqueda HR

### Query
```
HR manager manufactura
```

### Resultado Problemático
- **Candidato mostrado:** Director General
- **Problema:** No tiene sentido como match prioritario para una búsqueda de recursos humanos

### Tipo de Error
**Falso positivo** - Candidato irrelevante aparece con score alto

### Hipótesis de Causa Raíz

#### 1. Similitud Semántica Demasiado Amplia
Los embeddings de "HR manager" y "Director General" pueden tener cierta proximidad porque:
- Ambos son roles de gestión/liderazgo
- El embedding captura "manager" como concepto gerencial
- OpenAI text-embedding-3-small puede no discriminar bien entre áreas funcionales

#### 2. Keyword Matching Parcial
El sistema actual busca coincidencias en:
- `full_name`, `current_title`, `current_company`, `ai_summary`, `skills`
- "manufactura" puede coincidir con la industria del Director General
- El boost de keyword+semántico (+20) puede estar inflando el score

#### 3. Falta de Peso en Área Funcional
El `hybrid_search_service` actual:
- NO penaliza cuando el `functional_area` del candidato no coincide con la query
- "general_management" vs "human_resources" no tiene discriminación explícita

#### 4. Match Score Breakdown (a revisar mañana)
Necesitamos ver exactamente qué componentes empujaron al Director General:
```json
{
  "keyword_score": ?,
  "semantic_score": ?,
  "boosted": ?
}
```

---

## Diagnóstico a Realizar Mañana

### 1. Reproducir el caso exacto
```bash
curl -s "$API_URL/api/search/hybrid?query=HR%20manager%20manufactura" | jq '.results[] | {name: .full_name, title: .current_title, area: .functional_area, score: .match_score, breakdown: .match_breakdown}'
```

### 2. Analizar el embedding
- Comparar embedding de "HR manager manufactura" vs perfil del Director General
- Ver qué tan cerca están en el espacio vectorial

### 3. Revisar la taxonomía
- ¿El candidato tiene `functional_area` correctamente clasificado?
- ¿El AI clasificó bien a ese Director General como "general_management"?

### 4. Revisar el prompt de clasificación
- `/app/backend/atlas_service.py` → método `classify_candidate`
- ¿El AI está asignando áreas funcionales correctamente?

---

## Propuestas de Ajuste (NO implementar hoy)

### Opción A: Mayor peso a coincidencia de área funcional
```python
# En hybrid_search_service.py
FUNCTIONAL_AREA_BOOST = 15  # Nuevo boost cuando área coincide
FUNCTIONAL_AREA_PENALTY = -20  # Penalización cuando área NO coincide
```

### Opción B: Detección de área funcional en query
```python
# Detectar si el query menciona un área funcional conocida
AREA_KEYWORDS = {
    'human_resources': ['hr', 'recursos humanos', 'rh', 'talento'],
    'finance': ['cfo', 'finanzas', 'contabilidad'],
    'operations': ['operaciones', 'coo', 'supply chain'],
    # ...
}

# Si query contiene "HR", priorizar candidatos con functional_area="human_resources"
```

### Opción C: Mayor threshold para matches sin keyword
Actualmente: `MIN_MATCH_SCORE = 35`
- Si el candidato NO tiene keyword match directo, subir el threshold a 50+
- Evita que matches puramente semánticos aparezcan sin contexto textual

### Opción D: Castigo por discrepancia título-query
```python
# Si query menciona "HR manager" pero candidato es "Director General"
# Aplicar penalización porque el título principal no coincide
TITLE_MISMATCH_PENALTY = -15
```

### Opción E: Revisión del embedding model
- Considerar si text-embedding-3-small es suficiente para discriminación fina
- Alternativa: text-embedding-3-large (más costoso pero más preciso)

---

## Archivos a Revisar Mañana

| Archivo | Qué revisar |
|---------|-------------|
| `/app/backend/hybrid_search_service.py` | Lógica de scoring, thresholds, boosts |
| `/app/backend/atlas_service.py` | Prompt de clasificación de área funcional |
| `/app/backend/taxonomy.py` | Definición de áreas funcionales |
| `/app/backend/embedding_service.py` | Configuración del modelo de embeddings |

---

## Estado de la Sesión

- ✅ Unificación de búsqueda completada y testeada
- ✅ Arquitectura de búsqueda estable
- ⚠️ Relevancia/ranking necesita ajuste fino
- 🔜 Próximo paso: Afinar falsos positivos

---

## Queries de Validación Pendientes

Además de "HR manager manufactura", probar mañana:
1. `CFO manufactura` (0 resultados - ¿correcto o falso negativo?)
2. `recursos humanos` (sin industria)
3. `gerente de recursos humanos`
4. `director de finanzas retail`
5. `supply chain manager consumo`
