# Atlas Talent Vault - Propuesta de Scoring v2

## Fecha: 25-Mar-2026
## Estado: PROPUESTA (No implementar sin aprobación)

---

## 1. Diagnóstico del Sistema Actual

### Arquitectura Actual de Scoring
```
Score Final = (keyword_score × 0.9) + (semantic_score × 0.7) + boost_si_ambos(+20)
```

### Problemas Identificados

| Problema | Causa Raíz |
|----------|------------|
| CEOs/DGs aparecen en búsquedas funcionales | No hay penalización por área funcional incorrecta |
| Seniority alto rankea sobre función correcta | No hay matching de nivel jerárquico |
| Marketing y Ventas se mezclan | Funciones cercanas no tienen discriminación |
| Finance Manager → 0 resultados | Threshold muy alto o falta de candidatos |
| Experiencia secundaria pesa igual que primaria | No hay distinción de trayectoria principal |

---

## 2. Propuesta de Scoring Multi-Dimensional

### 2.1 Componentes del Score

```
SCORE_FINAL = (
    SCORE_FUNCIONAL      × 0.35   # Área funcional principal
  + SCORE_INDUSTRIA      × 0.15   # Coincidencia de industria
  + SCORE_SENIORITY      × 0.20   # Nivel jerárquico correcto
  + SCORE_SEMANTICO      × 0.15   # Similitud semántica general
  + SCORE_KEYWORDS       × 0.10   # Match textual directo
  + SCORE_TRAYECTORIA    × 0.05   # Consistencia de carrera
) + BOOSTS - PENALTIES
```

### 2.2 Distribución de Pesos (Propuesta)

| Componente | Peso | Justificación |
|------------|------|---------------|
| Área Funcional | 35% | Factor más importante en búsquedas funcionales |
| Seniority | 20% | Crítico para no mezclar niveles |
| Industria | 15% | Relevante pero transferible |
| Semántico | 15% | Captura similitudes no explícitas |
| Keywords | 10% | Coincidencias textuales directas |
| Trayectoria | 5% | Bonus por carrera consistente |

---

## 3. Detalle de Cada Componente

### 3.1 SCORE_FUNCIONAL (35%)

#### Definición
Mide qué tan bien coincide el área funcional principal del candidato con la búsqueda.

#### Matriz de Afinidad Funcional

```
                    Query →
Candidato ↓         HR    Finance  Ops    SC     Mkt    Sales  IT     Legal  GM
─────────────────────────────────────────────────────────────────────────────────
human_resources     100   10       10     10     10     15     10     10     30
finance             10    100      15     15     10     20     10     20     30
operations          10    15       100    70     10     15     15     10     40
supply_chain        10    10       70     100    10     15     10     10     30
marketing           15    10       10     10     100    60     20     10     25
sales               15    20       15     15     60     100    15     10     35
technology          10    15       20     20     20     15     100    10     25
legal               10    20       10     10     10     10     10     100    25
general_management  30    30       40     30     25     35     25     25     100
```

**Interpretación:**
- HR buscando HR = 100 puntos
- HR buscando General Management = 30 puntos
- General Management buscando HR = 30 puntos (no debería dominar)

#### Penalización por Función Incorrecta
```python
if candidato.functional_area == "general_management":
    if query_area in ["human_resources", "finance", "legal", "technology"]:
        PENALTY_GM_EN_FUNCION_ESPECIALIZADA = -25
```

### 3.2 SCORE_INDUSTRIA (15%)

#### Definición
Mide coincidencia de industria con bonus por industrias transferibles.

#### Matriz de Transferibilidad Industrial

```
                    Query →
Candidato ↓         Manuf  Retail  Pharma  Finance  Tech   Services  Consumer
─────────────────────────────────────────────────────────────────────────────
manufacturing       100    40      50      20       30     30        40
retail              40     100     30      30       40     50        80
pharmaceutical      50     30      100     30       40     40        30
financial_services  20     30      30      100      50     60        30
technology          30     40      40      50       100    60        40
professional_svc    30     50      40      60       60     100       40
consumer_goods      40     80      30      30       40     40        100
```

**Interpretación:**
- Retail → Consumer Goods = 80% transferible
- Manufacturing → Financial Services = 20% transferible

### 3.3 SCORE_SENIORITY (20%)

#### Jerarquía de Niveles (Índice 1-12)

| Nivel | Índice | Ejemplos |
|-------|--------|----------|
| Intern/Becario | 1 | Becario, Practicante |
| Auxiliar/Assistant | 2 | Auxiliar, Asistente |
| Analista | 3 | Analista Jr, Analista |
| Coordinador | 4 | Coordinador, Especialista |
| Supervisor | 5 | Supervisor, Team Lead |
| Jefatura/Lead | 6 | Jefe de área, Lead |
| Gerente/Manager | 7 | Gerente, Manager |
| Senior Manager | 8 | Sr. Manager, Gerente Sr. |
| Director | 9 | Director de área |
| VP | 10 | Vicepresidente |
| C-Level | 11 | CFO, COO, CMO, CTO |
| CEO/DG | 12 | CEO, Director General, Presidente |

#### Cálculo de Score de Seniority

```python
def calcular_score_seniority(nivel_candidato: int, nivel_query: int) -> float:
    """
    Penaliza desviaciones del nivel solicitado.
    Permite ±1 nivel con score completo, luego penaliza gradualmente.
    """
    diferencia = abs(nivel_candidato - nivel_query)
    
    if diferencia == 0:
        return 100  # Match exacto
    elif diferencia == 1:
        return 90   # ±1 nivel aceptable
    elif diferencia == 2:
        return 70   # ±2 niveles tolerable
    elif diferencia == 3:
        return 40   # ±3 niveles bajo
    else:
        return 10   # Muy lejos del nivel solicitado
```

#### Detección de Seniority en Query

```python
SENIORITY_KEYWORDS = {
    1: ["becario", "intern", "practicante"],
    2: ["auxiliar", "assistant", "asistente"],
    3: ["analista", "analyst"],
    4: ["coordinador", "coordinator", "especialista"],
    5: ["supervisor"],
    6: ["jefe", "lead", "jefatura"],
    7: ["gerente", "manager"],
    8: ["senior manager", "sr manager", "gerente senior"],
    9: ["director"],
    10: ["vp", "vicepresidente", "vice president"],
    11: ["cfo", "coo", "cmo", "cto", "cio", "chro", "c-level"],
    12: ["ceo", "director general", "presidente", "country manager"]
}
```

### 3.4 SCORE_SEMANTICO (15%)

#### Definición
Similitud coseno entre embedding de query y embedding del candidato.

#### Ajustes Propuestos
```python
# Actual
SEMANTIC_THRESHOLD = 0.30  # Muy permisivo

# Propuesto
SEMANTIC_THRESHOLD = 0.40  # Más selectivo
SEMANTIC_WEIGHT_REDUCTION_IF_NO_FUNCTIONAL_MATCH = 0.5  # Reducir peso si área no coincide
```

### 3.5 SCORE_KEYWORDS (10%)

#### Definición
Proporción de palabras clave de la query encontradas en el perfil del candidato.

#### Campos a Buscar (en orden de prioridad)
1. `current_title` (peso 3x)
2. `functional_area` (peso 2x)
3. `skills` (peso 2x)
4. `ai_summary` (peso 1x)
5. `previous_companies[].title` (peso 1x)

### 3.6 SCORE_TRAYECTORIA (5%)

#### Definición
Bonus por consistencia y progresión de carrera.

#### Indicadores
```python
def calcular_score_trayectoria(candidato: dict) -> float:
    score = 0
    
    # Años de experiencia apropiados para el nivel
    anos = candidato.get("years_experience", 0)
    seniority = candidato.get("seniority_index", 7)
    
    anos_esperados = {
        1: (0, 1), 2: (0, 2), 3: (1, 4), 4: (2, 6),
        5: (3, 8), 6: (4, 10), 7: (5, 15), 8: (8, 18),
        9: (10, 25), 10: (12, 30), 11: (15, 35), 12: (18, 40)
    }
    
    min_anos, max_anos = anos_esperados.get(seniority, (0, 50))
    if min_anos <= anos <= max_anos:
        score += 50  # Experiencia coherente con nivel
    
    # Progresión en empresas anteriores
    empresas = candidato.get("previous_companies", [])
    if len(empresas) >= 2:
        # Verificar que hubo progresión (no lateral puro)
        titulos = [e.get("title", "") for e in empresas]
        if tiene_progresion(titulos):
            score += 30
    
    # Consistencia funcional (carrera en misma área)
    areas_historicas = extraer_areas_de_historial(empresas)
    if es_carrera_consistente(areas_historicas, candidato.get("functional_area")):
        score += 20
    
    return score
```

---

## 4. Sistema de Boosts y Penalties

### 4.1 Boosts (Positivos)

| Boost | Valor | Condición |
|-------|-------|-----------|
| MATCH_EXACTO_FUNCION | +15 | Área funcional = área de query |
| MATCH_EXACTO_INDUSTRIA | +10 | Industria = industria de query |
| MATCH_EXACTO_SENIORITY | +10 | Nivel = nivel solicitado |
| KEYWORD_EN_TITULO | +10 | Query aparece en current_title |
| TRAYECTORIA_DESTACADA | +5 | Progresión clara y consistente |
| SKILL_MATCH_ALTO | +5 | 3+ skills coinciden con query |

### 4.2 Penalties (Negativos)

| Penalty | Valor | Condición |
|---------|-------|-----------|
| GM_EN_BUSQUEDA_FUNCIONAL | -25 | General Management en búsqueda de HR/Finance/etc |
| SENIORITY_MUY_ALTO | -20 | CEO/DG en búsqueda de Manager/Director |
| SENIORITY_MUY_BAJO | -15 | Analista en búsqueda de Director/VP |
| FUNCION_ADYACENTE_NO_PRINCIPAL | -10 | Ventas en búsqueda de Marketing (y viceversa) |
| INDUSTRIA_NO_TRANSFERIBLE | -10 | Industria muy diferente sin transferibilidad |
| SIN_EVIDENCIA_FUNCIONAL | -15 | Título y skills no muestran experiencia en área |

---

## 5. Algoritmo Propuesto

### Pseudocódigo

```python
def calcular_score_v2(query: str, candidato: dict) -> dict:
    # 1. Parsear query
    query_parsed = {
        "texto": query,
        "area_funcional": detectar_area_funcional(query),
        "industria": detectar_industria(query),
        "seniority": detectar_seniority(query),
        "keywords": extraer_keywords(query)
    }
    
    # 2. Calcular componentes
    scores = {
        "funcional": calcular_score_funcional(
            candidato["functional_area"], 
            query_parsed["area_funcional"]
        ),
        "industria": calcular_score_industria(
            candidato["industry"],
            query_parsed["industria"]
        ),
        "seniority": calcular_score_seniority(
            candidato["seniority_index"],
            query_parsed["seniority"]
        ),
        "semantico": calcular_similitud_coseno(
            query_embedding,
            candidato["embedding"]
        ),
        "keywords": calcular_match_keywords(
            query_parsed["keywords"],
            candidato
        ),
        "trayectoria": calcular_score_trayectoria(candidato)
    }
    
    # 3. Aplicar pesos
    score_ponderado = (
        scores["funcional"]   * 0.35 +
        scores["industria"]   * 0.15 +
        scores["seniority"]   * 0.20 +
        scores["semantico"]   * 0.15 +
        scores["keywords"]    * 0.10 +
        scores["trayectoria"] * 0.05
    )
    
    # 4. Aplicar boosts
    boosts = calcular_boosts(query_parsed, candidato, scores)
    
    # 5. Aplicar penalties
    penalties = calcular_penalties(query_parsed, candidato, scores)
    
    # 6. Score final
    score_final = max(0, min(100, score_ponderado + boosts - penalties))
    
    return {
        "match_score": round(score_final),
        "match_breakdown": {
            "funcional": round(scores["funcional"]),
            "industria": round(scores["industria"]),
            "seniority": round(scores["seniority"]),
            "semantico": round(scores["semantico"] * 100),
            "keywords": round(scores["keywords"]),
            "trayectoria": round(scores["trayectoria"]),
            "boosts": boosts,
            "penalties": penalties
        }
    }
```

---

## 6. Ejemplos de Aplicación

### Ejemplo 1: "HR Manager manufactura"

**Query parseada:**
```json
{
  "area_funcional": "human_resources",
  "industria": "manufacturing",
  "seniority": 7,  // Manager
  "keywords": ["hr", "manager", "manufactura"]
}
```

**Candidato A: Gerente de RRHH en Manufacturera**
```
Funcional: HR → HR = 100 × 0.35 = 35
Industria: Manufacturing → Manufacturing = 100 × 0.15 = 15
Seniority: 7 → 7 = 100 × 0.20 = 20
Semántico: 0.65 × 0.15 = 9.75
Keywords: 80 × 0.10 = 8
Trayectoria: 70 × 0.05 = 3.5
Boosts: +15 (match exacto función) +10 (match industria) = +25
Penalties: 0
TOTAL: 35 + 15 + 20 + 9.75 + 8 + 3.5 + 25 = 96.25 → 96
```

**Candidato B: CEO en Manufacturera (actual problema)**
```
Funcional: GM → HR = 30 × 0.35 = 10.5
Industria: Manufacturing → Manufacturing = 100 × 0.15 = 15
Seniority: 12 → 7 = 10 × 0.20 = 2  (5 niveles de diferencia)
Semántico: 0.45 × 0.15 = 6.75
Keywords: 30 × 0.10 = 3
Trayectoria: 50 × 0.05 = 2.5
Boosts: +10 (industria)
Penalties: -25 (GM en búsqueda funcional) -20 (seniority muy alto) = -45
TOTAL: 10.5 + 15 + 2 + 6.75 + 3 + 2.5 + 10 - 45 = 4.75 → 5
```

**Resultado:** HR Manager (96) >> CEO (5) ✅

### Ejemplo 2: "Marketing Manager B2B"

**Candidato C: Marketing Manager**
```
Funcional: Marketing → Marketing = 100 × 0.35 = 35
Seniority: 7 → 7 = 100 × 0.20 = 20
...
TOTAL: ~85
```

**Candidato D: Sales Manager**
```
Funcional: Sales → Marketing = 60 × 0.35 = 21
Seniority: 7 → 7 = 100 × 0.20 = 20
Penalties: -10 (función adyacente no principal)
...
TOTAL: ~55
```

**Resultado:** Marketing (85) > Sales (55) ✅ (Sales aparece pero más abajo)

---

## 7. Configuración Recomendada

### Thresholds

| Parámetro | Valor Actual | Valor Propuesto |
|-----------|--------------|-----------------|
| MIN_MATCH_SCORE | 35 | 40 |
| SEMANTIC_THRESHOLD | 0.30 | 0.40 |
| MAX_RESULTS | 50 | 30 |

### Feature Flags (para rollout gradual)

```python
SCORING_V2_ENABLED = True
SCORING_V2_WEIGHT_FUNCIONAL = 0.35
SCORING_V2_WEIGHT_SENIORITY = 0.20
SCORING_V2_PENALTY_GM = -25
SCORING_V2_PENALTY_SENIORITY_GAP = -20
```

---

## 8. Plan de Implementación

### Fase A: Preparación (1-2 horas)
1. Crear matrices de afinidad funcional e industrial
2. Implementar detección de área/seniority/industria en query
3. Agregar índice de seniority a modelo Candidate

### Fase B: Core Scoring (2-3 horas)
1. Refactorizar `hybrid_search_service.py` con nuevo algoritmo
2. Implementar cada componente de score
3. Agregar sistema de boosts/penalties

### Fase C: Testing (1-2 horas)
1. Probar con las 5 queries de validación
2. Comparar resultados v1 vs v2
3. Ajustar pesos según resultados

### Fase D: Rollout
1. Desplegar con feature flag
2. Validar con usuario
3. Ajustar según feedback

---

## 9. Evolución Futura: Motor de Matching

Esta propuesta sienta las bases para el futuro motor de matching vacante-candidato:

```
MATCHING_SCORE = (
    SCORE_FUNCIONAL        × peso_vacante
  + SCORE_INDUSTRIA        × peso_vacante
  + SCORE_SENIORITY        × peso_vacante
  + SCORE_SKILLS           × peso_vacante
  + SCORE_UBICACION        × peso_vacante
  + SCORE_SALARIO          × peso_vacante
  + SCORE_DISPONIBILIDAD   × peso_vacante
)
```

Donde `peso_vacante` es configurable por el reclutador según la prioridad de cada requisito.

---

## 10. Preguntas Pendientes

1. **¿Aprobar estos pesos iniciales?** (Funcional 35%, Seniority 20%, etc.)
2. **¿Qué tan estricta debe ser la penalización GM?** (-25 propuesto)
3. **¿Permitir resultados de funciones adyacentes?** (Marketing↔Ventas con penalty menor)
4. **¿Threshold mínimo de 40 es aceptable?** (filtraría más candidatos marginales)

---

## Archivos a Modificar

| Archivo | Cambios |
|---------|---------|
| `/app/backend/hybrid_search_service.py` | Reescribir algoritmo de scoring |
| `/app/backend/models.py` | Agregar `seniority_index`, ampliar `match_breakdown` |
| `/app/backend/taxonomy.py` | Agregar matrices de afinidad |
| `/app/backend/query_parser.py` | **NUEVO** - Parser de queries |
| `/app/backend/scoring_config.py` | **NUEVO** - Configuración de pesos |
