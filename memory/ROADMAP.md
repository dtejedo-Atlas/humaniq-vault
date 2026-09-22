# Humaniq Talent Vault — Pendientes

## P0 — Capas 1 y 2 completadas (2026-09-22)
- Capa 1: extracción DOCX/PDF/OCR corregida y 34 reprocesados con motor original. Resultado entregado antes de Capa 2: **34 legibles, 34 autoclasificados completos, cero ilegibles/pendientes**.
- Capa 2: segunda pasada condicional implementada, caché/deduplicación, cronología/industria/seniority, captura manual y botones individual/lote activos.
- Scoring/pesos/matching y primera pasada en atlas_service.py intactos. No se llamó a segunda pasada sobre los 34 ya resueltos.
- Pruebas: 47 regresiones finales + prueba real sintética previa de Claude/cache; no fallos funcionales pendientes del alcance.
- **NO integrar web**: el usuario lo pospuso expresamente. Reevaluar únicamente si aparecen suficientes casos reales no resueltos.

## P1 — Validación y medición
- Usuario valida una muestra de los 34 y nuevas cargas, especialmente identidad, industria y cronología; confianza IA no equivale a aprobación humana.
- Conservar los tests aislados como puerta de regresión. Prueba LLM real requiere opt-in explícito para no consumir saldo automáticamente.
- No repetir reprocesamientos ni introducir dashboards/features adicionales sin autorización.

## Operación anterior
- Baja de Patricia Sáez aplicada y cuenta conservada; acceso con sesión comprobado con HTTP 403.
- Verificación específica de login con contraseña correcta: pendiente porque no se dispone de esa contraseña. No restablecerla ni modificar el flujo de autenticación para fabricar un resultado 403.

## P1 — Validación del usuario
- Esperar exclusivamente ajustes y pruebas concretas que solicite el usuario durante el uso real.
- No ejecutar pruebas destructivas sobre la base compartida de producción.

## P2 — Congelado por instrucción del usuario
- Publicación externa de vacantes (Fase C) y tracking de origen de candidatos.
- Code quality, React hooks, componentes grandes y refactorizaciones.
- Retirar defaults de contraseñas antiguas en archivos de pruebas; no ejecutar sin autorización.
- Mejoras adicionales históricas: ver `CHANGELOG_LEGACY.md`; no reactivarlas automáticamente.

## P3 — Backlog, sin autorización de implementación
- Pestaña de auditoría/actividad en Usuarios.
- Botón para cerrar sesiones activas.
- Panel de salud del workspace.

## Posible mejora futura
- Comprobación automatizada de bajas usando cuentas sintéticas, sin necesitar contraseñas de exempleados. Solo considerar si el usuario la solicita.