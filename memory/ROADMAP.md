# Humaniq Talent Vault — Pendientes

## P0 — Operación solicitada (2026-09-22)
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