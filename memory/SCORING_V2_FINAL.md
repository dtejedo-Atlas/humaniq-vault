# Atlas Talent Vault - Modelo de Scoring v2.1 (Final)

## Fecha: 25-Mar-2026
## Estado: APROBADO PARA IMPLEMENTACIÓN

---

## 1. Distribución de Pesos (Ajustada)

```
SCORE_FINAL = (
    SCORE_FUNCIONAL      × 0.40   # ⬆️ Subido de 35% a 40%
  + SCORE_SENIORITY      × 0.20   # Mantiene 20%
  + SCORE_INDUSTRIA      × 0.15   # Mantiene 15%
  + SCORE_SEMANTICO      × 0.10   # ⬇️ Bajado de 15% a 10%
  + SCORE_KEYWORDS       × 0.08   # ⬇️ Bajado de 10% a 8%
  + SCORE_TRAYECTORIA    × 0.05   # Mantiene 5%
  + SCORE_ESTABILIDAD    × 0.02   # 🆕 Nuevo componente
) + BOOSTS - PENALTIES
```

### Resumen de Pesos

| Componente | Peso | Justificación |
|------------|------|---------------|
| **Área Funcional** | **40%** | Factor más crítico - función correcta > todo |
| **Seniority** | 20% | Nivel jerárquico correcto, con penalización por distancia |
| **Industria** | 15% | Relevante con transferibilidad |
| **Semántico** | 10% | Reducido - no debe dominar sobre función |
| **Keywords** | 8% | Match textual directo |
| **Trayectoria** | 5% | Progresión y consistencia de carrera |
| **Estabilidad** | 2% | Análisis de rotación laboral |
| **TOTAL** | 100% | |

---

## 2. SCORE_FUNCIONAL (40%)

### 2.1 Matriz de Afinidad Funcional

```
                         Query →
Candidato ↓              HR    FIN   OPS   SC    MKT   SALES  IT    LEGAL  GM
──────────────────────────────────────────────────────────────────────────────
human_resources          100   10    10    10    10    15     10    10     25
finance                  10    100   15    15    10    20     10    25     25
operations               10    15    100   70    10    15     15    10     35
supply_chain             10    10    70    100   10    15     10    10     30
marketing                15    10    10    10    100   55     20    10     20
sales                    15    20    15    15    55    100    15    10     30
technology               10    15    20    20    20    15     100   10     20
legal                    10    25    10    10    10    10     10    100    20
general_management       25    25    35    30    20    30     20    20     100
```

**Nota:** GM tiene afinidad reducida (25-35) hacia funciones especializadas.

### 2.2 Penalización GM Condicional

```python
def calcular_penalty_gm(candidato: dict, query_area: str) -> int:
    """
    Penaliza GM solo cuando NO hay evidencia funcional relevante.
    """
    if candidato.get("functional_area") != "general_management":
        return 0
    
    # Verificar si tiene evidencia funcional en la query area
    evidencia = tiene_evidencia_funcional(candidato, query_area)
    
    if evidencia == "fuerte":
        # GM con trayectoria sólida en la función → sin penalización
        # Ej: COO con 10 años en operaciones
        return 0
    elif evidencia == "moderada":
        # GM con algo de experiencia en la función → penalización leve
        # Ej: DG que lideró supply chain por 3 años
        return -10
    elif evidencia == "débil":
        # GM con mención superficial → penalización media
        return -20
    else:
        # GM sin evidencia funcional → penalización completa
        # Ej: CEO financiero buscando HR
        return -25


def tiene_evidencia_funcional(candidato: dict, query_area: str) -> str:
    """
    Analiza si el candidato GM tiene evidencia en el área buscada.
    Retorna: "fuerte", "moderada", "débil", "ninguna"
    """
    puntos = 0
    
    # 1. Revisar títulos anteriores
    for empresa in candidato.get("previous_companies", []):
        titulo = empresa.get("title", "").lower()
        if area_match_en_titulo(titulo, query_area):
            anos = empresa.get("years", 0)
            if anos >= 5:
                puntos += 40  # Trayectoria significativa
            elif anos >= 3:
                puntos += 25
            elif anos >= 1:
                puntos += 10
    
    # 2. Revisar skills
    skills_relevantes = contar_skills_del_area(candidato.get("skills", []), query_area)
    puntos += skills_relevantes * 5
    
    # 3. Revisar AI summary
    if area_mencionada_en_summary(candidato.get("ai_summary", ""), query_area):
        puntos += 15
    
    # Clasificar evidencia
    if puntos >= 50:
        return "fuerte"
    elif puntos >= 30:
        return "moderada"
    elif puntos >= 10:
        return "débil"
    else:
        return "ninguna"
```

---

## 3. SCORE_SENIORITY (20%)

### 3.1 Jerarquía de Niveles (Índice 1-12)

| Índice | Nivel | Ejemplos en Español | Ejemplos en Inglés |
|--------|-------|---------------------|-------------------|
| 1 | Becario | Becario, Practicante | Intern, Trainee |
| 2 | Auxiliar | Auxiliar, Asistente | Assistant, Support |
| 3 | Analista | Analista Jr/Sr | Analyst |
| 4 | Coordinador | Coordinador, Especialista | Coordinator, Specialist |
| 5 | Supervisor | Supervisor, Team Lead | Supervisor, Team Lead |
| 6 | Jefatura | Jefe de área, Lead | Head of, Lead |
| 7 | Gerente | Gerente, Manager | Manager |
| 8 | Sr. Manager | Gerente Senior, Sr. Manager | Senior Manager |
| 9 | Director | Director de área | Director |
| 10 | VP | Vicepresidente | Vice President, VP |
| 11 | C-Level | CFO, COO, CMO, CTO, CHRO | C-Suite |
| 12 | CEO/DG | CEO, Director General, Presidente | CEO, President, MD |

### 3.2 Scoring por Distancia de Nivel

```python
def calcular_score_seniority(nivel_candidato: int, nivel_query: int) -> float:
    """
    Scoring basado en distancia de nivel, no solo alto/bajo.
    
    Manager (7) vs Director (9) = diferencia 2 = 75 puntos (aceptable)
    Manager (7) vs CEO (12) = diferencia 5 = 0 puntos (inaceptable)
    """
    if nivel_query is None:
        # Query no especifica nivel → no penalizar
        return 80
    
    diferencia = abs(nivel_candidato - nivel_query)
    
    SCORES_POR_DISTANCIA = {
        0: 100,   # Match exacto
        1: 90,    # ±1 nivel → muy aceptable (Manager ↔ Sr. Manager)
        2: 75,    # ±2 niveles → aceptable (Manager ↔ Director)
        3: 50,    # ±3 niveles → cuestionable (Manager ↔ VP)
        4: 25,    # ±4 niveles → poco relevante
        5: 10,    # ±5 niveles → irrelevante (Manager ↔ CEO)
    }
    
    return SCORES_POR_DISTANCIA.get(diferencia, 0)
```

### 3.3 Ejemplo Práctico

| Query | Candidato | Diferencia | Score |
|-------|-----------|------------|-------|
| Manager (7) | Director (9) | 2 | 75 |
| Manager (7) | Sr. Manager (8) | 1 | 90 |
| Manager (7) | CEO (12) | 5 | 10 |
| Director (9) | VP (10) | 1 | 90 |
| Analista (3) | Gerente (7) | 4 | 25 |

---

## 4. SCORE_TRAYECTORIA (5%) - Ampliado

### 4.1 Componentes de Trayectoria

```python
def calcular_score_trayectoria(candidato: dict) -> float:
    """
    Analiza la trayectoria profesional del candidato.
    Retorna score de 0-100.
    """
    score = 0
    
    # === 1. AÑOS DE EXPERIENCIA vs NIVEL (25 puntos máx) ===
    anos = candidato.get("years_experience", 0)
    seniority = candidato.get("seniority_index", 7)
    
    RANGO_ESPERADO = {
        1: (0, 1),    # Becario: 0-1 años
        2: (0, 2),    # Auxiliar: 0-2 años
        3: (1, 4),    # Analista: 1-4 años
        4: (2, 6),    # Coordinador: 2-6 años
        5: (3, 8),    # Supervisor: 3-8 años
        6: (4, 10),   # Jefatura: 4-10 años
        7: (5, 15),   # Gerente: 5-15 años
        8: (8, 18),   # Sr. Manager: 8-18 años
        9: (10, 25),  # Director: 10-25 años
        10: (12, 30), # VP: 12-30 años
        11: (15, 35), # C-Level: 15-35 años
        12: (18, 40)  # CEO: 18-40 años
    }
    
    min_anos, max_anos = RANGO_ESPERADO.get(seniority, (0, 50))
    if min_anos <= anos <= max_anos:
        score += 25  # Experiencia coherente con nivel
    elif anos < min_anos:
        score += 10  # Ascenso rápido (puede ser positivo o riesgoso)
    else:
        score += 15  # Más experiencia de la típica
    
    # === 2. PROGRESIÓN DE CARRERA (25 puntos máx) ===
    empresas = candidato.get("previous_companies", [])
    if len(empresas) >= 2:
        if tiene_progresion_ascendente(empresas):
            score += 25  # Carrera con ascensos claros
        elif tiene_movimientos_laterales(empresas):
            score += 15  # Movimientos laterales (especialización)
        else:
            score += 5   # Sin progresión clara
    else:
        score += 10  # Poca historia laboral visible
    
    # === 3. DURACIÓN PROMEDIO POR EMPRESA (25 puntos máx) ===
    duracion_promedio = calcular_duracion_promedio(empresas, anos)
    
    if duracion_promedio >= 4:
        score += 25  # Estable (4+ años promedio)
    elif duracion_promedio >= 2.5:
        score += 20  # Buena estabilidad (2.5-4 años)
    elif duracion_promedio >= 1.5:
        score += 10  # Estabilidad moderada (1.5-2.5 años)
    else:
        score += 0   # Alta rotación (<1.5 años promedio)
    
    # === 4. CONSISTENCIA FUNCIONAL (25 puntos máx) ===
    area_actual = candidato.get("functional_area")
    areas_previas = extraer_areas_de_historial(empresas)
    
    consistencia = calcular_consistencia_funcional(area_actual, areas_previas)
    if consistencia >= 0.8:
        score += 25  # Carrera muy consistente en el área
    elif consistencia >= 0.5:
        score += 15  # Carrera mayormente en el área
    elif consistencia >= 0.3:
        score += 10  # Algo de experiencia en el área
    else:
        score += 5   # Carrera diversa / cambio de área
    
    return score  # Máximo 100


def tiene_progresion_ascendente(empresas: list) -> bool:
    """
    Verifica si hubo ascensos en la trayectoria.
    """
    niveles = [inferir_nivel_de_titulo(e.get("title", "")) for e in empresas]
    niveles = [n for n in niveles if n > 0]  # Filtrar no detectados
    
    if len(niveles) < 2:
        return False
    
    # Verificar tendencia ascendente
    ascensos = sum(1 for i in range(1, len(niveles)) if niveles[i] > niveles[i-1])
    return ascensos >= len(niveles) // 2


def calcular_duracion_promedio(empresas: list, anos_totales: int) -> float:
    """
    Calcula duración promedio en cada empresa.
    """
    if not empresas:
        return anos_totales  # Si no hay historial, asumir todo en una empresa
    
    num_empresas = len(empresas) + 1  # +1 por empresa actual
    return anos_totales / num_empresas if num_empresas > 0 else 0
```

### 4.2 Etapa Profesional Estimada

```python
def estimar_etapa_profesional(candidato: dict) -> str:
    """
    Estima la etapa profesional del candidato.
    """
    anos = candidato.get("years_experience", 0)
    seniority = candidato.get("seniority_index", 7)
    
    if anos <= 3:
        return "early_career"       # Inicio de carrera
    elif anos <= 8:
        return "developing"         # En desarrollo
    elif anos <= 15:
        return "mid_career"         # Carrera media / consolidación
    elif anos <= 25:
        return "senior"             # Senior / madurez
    else:
        return "executive"          # Ejecutivo / final de carrera
```

---

## 5. SCORE_ESTABILIDAD (2%) - NUEVO

### 5.1 Cálculo de Estabilidad

```python
def calcular_score_estabilidad(candidato: dict) -> tuple[float, str]:
    """
    Analiza estabilidad laboral del candidato.
    Retorna (score, warning_level).
    
    warning_level: "none", "low", "moderate", "high"
    """
    anos = candidato.get("years_experience", 0)
    empresas = candidato.get("previous_companies", [])
    num_empleos = len(empresas) + 1  # +1 por empleo actual
    
    if anos == 0:
        return (50, "none")  # Sin datos suficientes
    
    # Ratio de empleos por año
    ratio = num_empleos / anos
    
    # Thresholds de estabilidad
    if ratio <= 0.25:
        # ≤1 empleo cada 4 años → muy estable
        return (100, "none")
    elif ratio <= 0.4:
        # ≤1 empleo cada 2.5 años → estable
        return (85, "none")
    elif ratio <= 0.6:
        # ≤1 empleo cada 1.7 años → moderado
        return (60, "low")
    elif ratio <= 0.8:
        # ≤1 empleo cada 1.25 años → alerta moderada
        return (40, "moderate")
    else:
        # >1 empleo por año → alerta alta
        return (20, "high")


# Ejemplos:
# 3 empleos en 10 años = ratio 0.3 → (85, "none")
# 5 empleos en 10 años = ratio 0.5 → (60, "low")
# 5 empleos en 3 años = ratio 1.67 → (20, "high")
# 8 empleos en 15 años = ratio 0.53 → (60, "low")
```

### 5.2 Penalty por Inestabilidad

```python
def calcular_penalty_estabilidad(warning_level: str) -> int:
    """
    Penalty leve basado en nivel de alerta.
    NO descarta candidatos, solo ajusta ranking.
    """
    PENALTIES = {
        "none": 0,
        "low": -2,
        "moderate": -5,
        "high": -8
    }
    return PENALTIES.get(warning_level, 0)
```

### 5.3 Warning en Respuesta

```python
# El warning se incluye en match_breakdown para UI
{
    "match_score": 72,
    "match_breakdown": {
        "funcional": 85,
        "seniority": 90,
        "industria": 70,
        # ...
        "estabilidad": {
            "score": 40,
            "warning": "moderate",
            "detalle": "5 empleos en 6 años"
        }
    }
}
```

---

## 6. Sistema de Boosts y Penalties (Actualizado)

### 6.1 Boosts

| Boost | Valor | Condición |
|-------|-------|-----------|
| MATCH_EXACTO_FUNCION | +12 | área funcional = área de query |
| MATCH_EXACTO_INDUSTRIA | +8 | industria = industria de query |
| MATCH_EXACTO_SENIORITY | +8 | nivel = nivel solicitado |
| KEYWORD_EN_TITULO_ACTUAL | +10 | Query aparece en current_title |
| TRAYECTORIA_CONSISTENTE | +5 | Carrera >80% en misma función |
| SKILLS_MATCH_ALTO | +4 | 4+ skills coinciden |

### 6.2 Penalties

| Penalty | Valor | Condición |
|---------|-------|-----------|
| GM_SIN_EVIDENCIA_FUNCIONAL | -25 | GM sin trayectoria en área buscada |
| GM_EVIDENCIA_DEBIL | -20 | GM con mención superficial |
| GM_EVIDENCIA_MODERADA | -10 | GM con algo de experiencia |
| SENIORITY_DISTANCIA_5+ | -15 | 5+ niveles de diferencia |
| SENIORITY_DISTANCIA_4 | -8 | 4 niveles de diferencia |
| FUNCION_ADYACENTE | -8 | Marketing↔Ventas, Ops↔SC |
| INDUSTRIA_NO_TRANSFERIBLE | -6 | Industria muy diferente |
| ESTABILIDAD_HIGH | -8 | >1 empleo/año |
| ESTABILIDAD_MODERATE | -5 | Rotación moderada |

---

## 7. Configuración Final

### 7.1 Thresholds

| Parámetro | Valor |
|-----------|-------|
| **MIN_MATCH_SCORE** | **45** ⬆️ (era 35) |
| SEMANTIC_THRESHOLD | 0.40 |
| MAX_RESULTS | 30 |

### 7.2 Feature Flags

```python
# /app/backend/scoring_config.py

SCORING_V2_ENABLED = True

# Pesos principales
WEIGHT_FUNCIONAL = 0.40
WEIGHT_SENIORITY = 0.20
WEIGHT_INDUSTRIA = 0.15
WEIGHT_SEMANTICO = 0.10
WEIGHT_KEYWORDS = 0.08
WEIGHT_TRAYECTORIA = 0.05
WEIGHT_ESTABILIDAD = 0.02

# Thresholds
MIN_MATCH_SCORE = 45
SEMANTIC_THRESHOLD = 0.40

# Penalties
PENALTY_GM_SIN_EVIDENCIA = -25
PENALTY_GM_EVIDENCIA_DEBIL = -20
PENALTY_GM_EVIDENCIA_MODERADA = -10
PENALTY_SENIORITY_5_NIVELES = -15
PENALTY_FUNCION_ADYACENTE = -8
PENALTY_ESTABILIDAD_HIGH = -8
```

---

## 8. Ejemplos Completos

### Ejemplo 1: "HR Manager manufactura"

**Query parseada:**
```json
{
  "area_funcional": "human_resources",
  "industria": "manufacturing", 
  "seniority_index": 7,
  "keywords": ["hr", "manager", "manufactura"]
}
```

#### Candidato A: Gerente de RRHH en Manufacturera
```
FUNCIONAL:    HR → HR = 100 × 0.40 = 40.0
SENIORITY:    7 → 7 = 100 × 0.20 = 20.0
INDUSTRIA:    Manuf → Manuf = 100 × 0.15 = 15.0
SEMÁNTICO:    0.70 × 100 × 0.10 = 7.0
KEYWORDS:     90 × 0.08 = 7.2
TRAYECTORIA:  85 × 0.05 = 4.25
ESTABILIDAD:  85 × 0.02 = 1.7
─────────────────────────────────
SUBTOTAL:     95.15

BOOSTS:
+ Match exacto función: +12
+ Match exacto industria: +8
+ Match exacto seniority: +8
= +28

PENALTIES: 0
─────────────────────────────────
TOTAL: 95.15 + 28 = 123.15 → CAP 100 = **100**
```

#### Candidato B: CEO en Manufacturera (problema actual)
```
FUNCIONAL:    GM → HR = 25 × 0.40 = 10.0
SENIORITY:    12 → 7 = 10 × 0.20 = 2.0  (5 niveles diferencia)
INDUSTRIA:    Manuf → Manuf = 100 × 0.15 = 15.0
SEMÁNTICO:    0.45 × 100 × 0.10 = 4.5
KEYWORDS:     20 × 0.08 = 1.6
TRAYECTORIA:  70 × 0.05 = 3.5
ESTABILIDAD:  85 × 0.02 = 1.7
─────────────────────────────────
SUBTOTAL:     38.3

BOOSTS:
+ Match industria: +8
= +8

PENALTIES:
- GM sin evidencia funcional: -25
- Seniority 5+ niveles: -15
= -40
─────────────────────────────────
TOTAL: 38.3 + 8 - 40 = 6.3 → **6**
```

**Resultado: HR Manager (100) >> CEO (6)** ✅

---

### Ejemplo 2: "Marketing Manager B2B"

#### Candidato C: Marketing Manager en Consumo
```
FUNCIONAL:    Mkt → Mkt = 100 × 0.40 = 40.0
SENIORITY:    7 → 7 = 100 × 0.20 = 20.0
INDUSTRIA:    Consumer → ? = 70 × 0.15 = 10.5
SEMÁNTICO:    0.65 × 100 × 0.10 = 6.5
KEYWORDS:     80 × 0.08 = 6.4
TRAYECTORIA:  75 × 0.05 = 3.75
ESTABILIDAD:  85 × 0.02 = 1.7
─────────────────────────────────
SUBTOTAL:     88.85

BOOSTS: +12 (función) + +8 (seniority) = +20
PENALTIES: 0
─────────────────────────────────
TOTAL: 88.85 + 20 = **108.85 → 100**
```

#### Candidato D: Sales Manager en Retail
```
FUNCIONAL:    Sales → Mkt = 55 × 0.40 = 22.0
SENIORITY:    7 → 7 = 100 × 0.20 = 20.0
INDUSTRIA:    Retail → ? = 60 × 0.15 = 9.0
SEMÁNTICO:    0.55 × 100 × 0.10 = 5.5
KEYWORDS:     40 × 0.08 = 3.2
TRAYECTORIA:  70 × 0.05 = 3.5
ESTABILIDAD:  85 × 0.02 = 1.7
─────────────────────────────────
SUBTOTAL:     64.9

BOOSTS: +8 (seniority) = +8
PENALTIES: -8 (función adyacente) = -8
─────────────────────────────────
TOTAL: 64.9 + 8 - 8 = **64.9 → 65**
```

**Resultado: Marketing (100) > Sales (65)** ✅
(Sales aparece pero 35 puntos más abajo)

---

### Ejemplo 3: "COO con trayectoria en operaciones" buscando "Operations Manager"

#### Candidato E: COO que fue Director de Operaciones por 8 años
```
FUNCIONAL:    GM → Ops = 35 × 0.40 = 14.0  (base GM→Ops)
SENIORITY:    11 → 7 = 25 × 0.20 = 5.0  (4 niveles)
INDUSTRIA:    Manuf → Manuf = 100 × 0.15 = 15.0
SEMÁNTICO:    0.70 × 100 × 0.10 = 7.0
KEYWORDS:     70 × 0.08 = 5.6
TRAYECTORIA:  90 × 0.05 = 4.5
ESTABILIDAD:  100 × 0.02 = 2.0
─────────────────────────────────
SUBTOTAL:     53.1

BOOSTS: +8 (industria) = +8

PENALTIES:
- GM evidencia FUERTE → 0 (no se penaliza por trayectoria)
- Seniority 4 niveles: -8
= -8
─────────────────────────────────
TOTAL: 53.1 + 8 - 8 = **53.1 → 53**
```

Este COO con experiencia operativa real rankea decentemente (53), pero un Operations Manager directo (con score ~90+) lo superará claramente.

---

## 9. Arquitectura de Búsqueda (Confirmación)

### Jerarquía de Vistas

| Vista | Rol | Motor de Búsqueda |
|-------|-----|-------------------|
| **`/search`** | **PRINCIPAL** - Búsqueda avanzada | Scoring v2.1 completo |
| `/candidates` | Secundaria - Navegación/gestión | Scoring v2.1 (simplificado) |
| `/dashboard` | Info - Solo estadísticas | Sin búsqueda |

### Futuro de `/search`

- Filtros avanzados (múltiples industrias, rangos de experiencia)
- Parámetros de peso configurables por usuario
- Modo "matching" contra perfil de vacante
- Guardado de búsquedas frecuentes

---

## 10. Roadmap: Descarga de CVs

### Fase Futura (no implementar ahora)

```python
# Endpoint propuesto
@api_router.get("/candidates/{candidate_id}/resume/download")
async def download_resume(
    candidate_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
):
    """
    Descarga CV del candidato.
    - Solo admins pueden descargar
    - Se registra tracking de descarga
    """
    # Log de descarga
    await db.download_logs.insert_one({
        "candidate_id": candidate_id,
        "user_id": current_user.id,
        "downloaded_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Retornar archivo
    ...
```

---

## 11. Archivos a Crear/Modificar

### Nuevos Archivos

| Archivo | Descripción |
|---------|-------------|
| `/app/backend/scoring_config.py` | Configuración de pesos y thresholds |
| `/app/backend/query_parser.py` | Parser de queries (detecta área, seniority, industria) |
| `/app/backend/affinity_matrices.py` | Matrices de afinidad funcional e industrial |
| `/app/backend/trajectory_analyzer.py` | Análisis de trayectoria y estabilidad |

### Archivos a Modificar

| Archivo | Cambios |
|---------|---------|
| `/app/backend/hybrid_search_service.py` | Reescribir con scoring v2.1 |
| `/app/backend/models.py` | Agregar `seniority_index`, `stability_warning` |
| `/app/backend/taxonomy.py` | Agregar keywords de seniority |

---

## 12. Plan de Implementación

### Fase A: Infraestructura (1-2 horas)
1. Crear `scoring_config.py` con pesos y thresholds
2. Crear `affinity_matrices.py` con matrices
3. Crear `query_parser.py` con detección de área/seniority/industria

### Fase B: Análisis de Candidatos (1-2 horas)
1. Crear `trajectory_analyzer.py` con lógica de trayectoria
2. Agregar cálculo de `seniority_index` a candidatos
3. Implementar análisis de estabilidad

### Fase C: Scoring Principal (2-3 horas)
1. Refactorizar `hybrid_search_service.py` con nuevo algoritmo
2. Implementar cada componente de score
3. Implementar sistema de boosts/penalties condicionales

### Fase D: Testing (1-2 horas)
1. Probar con las 5 queries originales
2. Verificar que HR > CEO, Marketing > Sales
3. Validar warnings de estabilidad

---

## 13. Aprobación

| Criterio | Estado |
|----------|--------|
| Peso funcional 40% | ✅ Aprobado |
| Seniority por distancia | ✅ Aprobado |
| GM penalty condicional | ✅ Aprobado |
| Threshold 45 | ✅ Aprobado |
| Funciones adyacentes con penalty | ✅ Aprobado |
| Trayectoria ampliada | ✅ Aprobado |
| Estabilidad como nuevo componente | ✅ Aprobado |
| /search como buscador principal | ✅ Confirmado |

**LISTO PARA IMPLEMENTAR**
