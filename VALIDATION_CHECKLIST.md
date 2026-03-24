# 📋 Atlas Talent Vault - Checklist de Validación Fase 1.5

## 🎯 Objetivo
Validar calidad de Atlas IA con 50-100 CVs reales antes de Fase 2.

---

## ✅ Checklist por CV Cargado

### 1. PARSING (Extracción de Datos)
Revisar que Atlas extrajo correctamente:

- [ ] **Nombre completo** - ¿Correcto y completo?
- [ ] **Email** - ¿Extraído correctamente?
- [ ] **Teléfono** - ¿Formato correcto?
- [ ] **Ciudad/Estado/País** - ¿Ubicación correcta?
- [ ] **Puesto actual** - ¿Título extraído correctamente?
- [ ] **Empresa actual** - ¿Nombre de empresa correcto?
- [ ] **Años de experiencia** - ¿Número razonable?
- [ ] **Skills** - ¿Lista de habilidades relevantes?
- [ ] **Idiomas** - ¿Idiomas mencionados?
- [ ] **Historial laboral** - ¿Empresas previas con títulos?

**Calificación de Parsing:**
- 5/5: Todos los campos extraídos correctamente
- 4/5: 1-2 campos menores incorrectos
- 3/5: 3-4 campos incorrectos o faltantes
- 2/5: Muchos datos incorrectos
- 1/5: Parsing casi completamente fallido

---

### 2. CLASIFICACIÓN POR INDUSTRIA
Atlas debe asignar industria basada en experiencia.

**Industrias disponibles:**
- Manufacturing
- Consumer Goods
- Retail
- Logistics and Supply Chain
- Transportation
- Pharmaceutical
- Construction
- Real Estate
- Financial Services
- Technology
- Hospitality
- Industrial Services
- Energy
- Automotive
- Food and Beverage
- Professional Services
- Healthcare

**Evaluar:**
- [ ] ¿La industria asignada por Atlas tiene sentido?
- [ ] ¿Coincide con el historial laboral principal?
- [ ] Si hay múltiples industrias, ¿eligió la más relevante?

**Resultado:** ✅ Correcto | ❌ Incorrecto | ⚠️ Discutible

---

### 3. CLASIFICACIÓN POR ÁREA FUNCIONAL
Atlas debe identificar la función principal del candidato.

**Áreas disponibles:**
- General Management
- Operations
- Manufacturing
- Supply Chain
- Logistics
- Procurement
- Sales
- Business Development
- Marketing
- Finance
- Accounting
- Human Resources
- Talent Acquisition
- Engineering
- Quality
- Maintenance
- IT
- Legal
- Customer Service
- Project Management
- Construction Management

**Evaluar:**
- [ ] ¿El área funcional refleja su rol principal?
- [ ] ¿Es consistente con sus últimos 2-3 puestos?
- [ ] Si tiene experiencia en múltiples áreas, ¿eligió la más senior/reciente?

**Resultado:** ✅ Correcto | ❌ Incorrecto | ⚠️ Discutible

---

### 4. CLASIFICACIÓN DE SENIORITY
Atlas debe determinar nivel de liderazgo.

**Niveles:**
- Entry/Junior (0-3 años, Analyst, Assistant)
- Mid (3-5 años, Specialist, Coordinator)
- Senior (5-8 años, Senior Specialist)
- Lead (8-10 años, Team Lead, Senior Manager)
- Manager (Manager, Jefe)
- Director (Director, Head of)
- VP (Vice President)
- C-Level (CEO, CFO, COO, etc.)

**Evaluar:**
- [ ] ¿El seniority coincide con años de experiencia?
- [ ] ¿Refleja el título actual correctamente?
- [ ] ¿Es realista para el tipo de empresa/industria?

**Resultado:** ✅ Correcto | ❌ Incorrecto | ⚠️ Discutible

---

### 5. RESUMEN GENERADO POR ATLAS
Revisar calidad del resumen profesional.

**Criterios:**
- [ ] ¿Resume fortalezas clave del candidato?
- [ ] ¿Es conciso (3-4 oraciones)?
- [ ] ¿Destaca experiencia relevante?
- [ ] ¿Está en español profesional?
- [ ] ¿Es útil para un reclutador?

**Calificación:** 5⭐ Excelente | 4⭐ Bueno | 3⭐ Aceptable | 2⭐ Pobre | 1⭐ Inútil

---

### 6. DETECCIÓN DE DUPLICADOS
Probar subiendo el mismo candidato 2 veces.

**Escenarios a probar:**
- [ ] Mismo email → ¿Detecta 100% confianza?
- [ ] Mismo LinkedIn → ¿Detecta 95% confianza?
- [ ] Mismo teléfono → ¿Detecta 90% confianza?
- [ ] Nombre similar + empresa común → ¿Detecta 70-85%?
- [ ] CV diferente del mismo candidato → ¿Sugiere fusión?

**Resultado:** ✅ Detectó correctamente | ❌ No detectó | ⚠️ Falso positivo

---

### 7. BÚSQUEDA HÍBRIDA (KEYWORD)
Probar búsqueda con términos exactos.

**Queries de prueba:**
- Nombre del candidato
- Empresa actual
- Título exacto
- Skill específico

**Evaluar:**
- [ ] ¿Aparece el candidato en resultados?
- [ ] ¿Posición razonable en ranking?
- [ ] ¿Tiempo de respuesta <1s?

**Resultado:** ✅ Funciona bien | ❌ No funciona | ⚠️ Resultados pobres

---

### 8. BÚSQUEDA SEMÁNTICA (IA)
Probar búsqueda con lenguaje natural.

**Queries reales de reclutamiento:**
1. "CFO con experiencia en manufactura"
2. "Director de operaciones sector automotriz"
3. "Gerente de supply chain con background en retail"
4. "Ingeniero senior con experiencia en proyectos de construcción"
5. "Head of marketing para empresa tecnológica"

**Para cada candidato relevante:**
- [ ] ¿Aparece en búsquedas relacionadas a su perfil?
- [ ] ¿Match score >60% para queries muy relevantes?
- [ ] ¿Match score 40-60% para queries parcialmente relevantes?
- [ ] ¿NO aparece en queries irrelevantes?

**Evaluar:**
- [ ] Relevancia: ¿Los resultados tienen sentido?
- [ ] Ranking: ¿Los mejores matches están arriba?
- [ ] Cobertura: ¿Encuentra perfiles aunque usen otras palabras?

**Resultado:** ✅ Alta relevancia | ⚠️ Relevancia media | ❌ Pobre relevancia

---

## 📊 Métricas a Capturar

### Métricas Globales (después de 50-100 CVs)

1. **Precisión de Clasificación:**
   - % Industria correcta
   - % Área funcional correcta
   - % Seniority correcto

2. **Calidad de Parsing:**
   - Promedio de calificación (1-5)
   - % de CVs con parsing perfecto (5/5)
   - Campos problemáticos frecuentes

3. **Búsqueda:**
   - % de búsquedas con resultados útiles
   - Tiempo promedio de respuesta
   - Casos donde semántica es superior a keyword

4. **Duplicados:**
   - % de duplicados correctamente detectados
   - % de falsos positivos
   - Confianza promedio en detecciones

---

## 🚨 Errores Frecuentes a Documentar

**Clasificación:**
- Industria X confundida con Y
- Área funcional Z asignada incorrectamente cuando...
- Seniority subestimado/sobreestimado en casos de...

**Parsing:**
- Campo X no extraído en CVs de formato Y
- Nombres con caracteres especiales
- Fechas en formato no reconocido

**Búsqueda:**
- Query X no encuentra candidatos obvios
- Match scores demasiado bajos/altos
- Resultados irrelevantes en búsquedas de...

---

## 🎯 Criterios de Éxito para Fase 1.5

**Mínimo aceptable para avanzar a Fase 2:**
- ✅ Precisión industria: ≥70%
- ✅ Precisión área funcional: ≥70%
- ✅ Precisión seniority: ≥65%
- ✅ Parsing promedio: ≥3.5/5
- ✅ Búsquedas relevantes: ≥75%
- ✅ Duplicados detectados: ≥85%

**Óptimo:**
- 🎯 Precisión industria: ≥85%
- 🎯 Precisión área funcional: ≥85%
- 🎯 Precisión seniority: ≥80%
- 🎯 Parsing promedio: ≥4.2/5
- 🎯 Búsquedas relevantes: ≥85%
- 🎯 Duplicados detectados: ≥95%

---

## 📝 Proceso de Validación Recomendado

### Día 1-2: Carga inicial (20-30 CVs)
1. Seleccionar CVs representativos de tu base real
2. Subir uno por uno a través de la UI
3. Revisar cada candidato inmediatamente después de procesado
4. Registrar evaluación en sistema de validación
5. Documentar errores obvios

### Día 3-4: Carga masiva (30-40 CVs)
1. Subir en lotes más grandes
2. Validar clasificaciones en batch
3. Probar detección de duplicados
4. Ejecutar queries de búsqueda

### Día 5: Análisis y búsquedas
1. Revisar tablero de validación
2. Ejecutar 10-15 búsquedas reales de reclutamiento
3. Evaluar relevancia de resultados
4. Documentar casos problemáticos

### Día 6-7: Ajustes y validación final
1. Analizar métricas globales
2. Identificar patrones de error
3. Decidir si se cumplen criterios mínimos
4. Documentar ajustes necesarios para Fase 2

---

## 🔧 Cómo Registrar Validación

**En cada candidato:**
1. Ir a perfil del candidato
2. Revisar clasificación de Atlas
3. Evaluar correctitud
4. Agregar comentarios si hay errores
5. Guardar registro

**En búsquedas:**
1. Ejecutar query
2. Revisar top 5 resultados
3. Evaluar relevancia
4. Documentar en sistema

**Exportar datos:**
- Usar botón "Exportar CSV" en página de Validación
- Analizar en Excel/Google Sheets
- Compartir con equipo

---

## 📌 Notas Importantes

- **No juzgar con 1-2 CVs:** Necesitas volumen para ver patrones
- **Documentar edge cases:** Los casos raros son los más valiosos
- **Ser objetivo:** No confirmar lo que quieres ver
- **Comparar con expectativas reales:** ¿Un reclutador humano lo clasificaría así?
- **Considerar contexto:** Algunos perfiles son genuinamente ambiguos

---

**Esta validación es crítica para decidir si Atlas está listo para operación multiusuario real.**
