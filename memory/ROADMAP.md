# Humaniq Talent Vault — Pendientes

## P0 — Segunda pasada pendiente de autorización (2026-09-22)
- Diagnóstico de 34 CVs completado y entregado. Secciones 3/4 implementadas y probadas; scoring/pesos/matching intactos.
- Esperar OK explícito antes de mejorar extracción/OCR o clasificación. NO ejecutar aún una segunda pasada ni reprocesar los 34.
- Propuesta: umbral <0,75 o claves/campos ausentes; recuperar DOCX/PDF/OCR primero, CV completo, industria dominante de última década, seniority por evidencia y años sin doble conteo; una pasada adicional deduplicada por versión y caché de empresas.
- Decidir integración web solo para empresas desconocidas: disponible para el agente, no actualmente para la app.
- Implementar estados de captura manual y avisos de ilegibilidad junto con la segunda pasada; conectar entonces controles individuales/masivos ya visibles y deshabilitados.
- Mejora relevante prioritaria: recuperar texto omitido antes de gastar llamadas LLM adicionales.

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