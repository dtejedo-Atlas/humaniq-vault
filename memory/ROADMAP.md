# Humaniq Talent Vault — Pendientes

## P0 — Decisiones del usuario pendientes (2026-10-20)
- **No quedan cuentas de prueba activas en producción**: para cualquier verificación futura hay que pedirle al usuario que reactive `test_utf8@atlas.com` o cree una cuenta de prueba nueva.
- **Las 3 consultoras (Ximena, Alejandra, Berenice) deben aceptar su invitación antes del 27-oct**; si vence, reenviarla desde Usuarios.
- **Confirmación pendiente del usuario**: que sus dos cuentas (diego@humaniq.com.mx y dtejedo@gmail.com) entren en vault.humaniq.com.mx (no tenemos sus contraseñas, así que el agente no pudo probarlas; el arreglo de CORS es independiente de la cuenta y se validó con cuentas de prueba en escritorio y celular).
- **Login con Google desde el dominio propio**: pendiente de confirmar si Emergent Auth necesita autorizar vault.humaniq.com.mx.
- **Reglas del piloto vigentes**: nada de scripts que escriban en la base ni pruebas contra ella sin aprobación; si una consultora reporta un error, diagnóstico de solo lectura y reporte, sin correcciones en caliente.

## P0 — Decisiones anteriores (2026-10-19)
- **Primera tarea después del piloto**: "olvidé mi contraseña" autoservicio (endpoint público con respuesta genérica que no revela si el correo existe, límite de intentos por correo/IP, token de un solo uso con enlace al dominio propio y revocación de sesiones al cambiar contraseña). Durante el piloto el reset lo dispara el admin desde Usuarios (decisión del usuario, 19-oct).
- **Revocación de sesiones JWT** al cambiar o restablecer contraseña: sigue pendiente (hoy los JWT viven 7 días sin revocación). No tocar la autenticación durante el piloto.

## P0 — Decisiones anteriores (2026-10-14)
- **Audita y despliega**: código listo y probado en preview, **sin desplegar** por instrucción. El usuario pidió push a GitHub (botón "Save to Github" del chat) y auditar la lista de archivos antes del deploy.
- **135 fichas no fusionadas con el mismo empleo repetido**: RESUELTO el 14-oct. Causa raíz corregida en código y 128 fichas limpiadas (831 empleos). Quedan **7 fichas para revisión manual** (Luis Fernando Rojas Torres, Juan José Hernández, Alejandro Arellano Flores, Ana Lucia Treviño Gómez, Angel Gutierrez, Anel Lizbeth Díaz Prado, Daniela Alejandra Aguilar Aguilar): 12 empleos repetidos sin evidencia de limpieza de CV idéntico.
- **92 fichas sintéticas de prueba en Atlas**, todas con borrado lógico: decidir si se purgan de verdad. Hoy no estorban al ranking.
- **Años de experiencia**: en 53 de las 128 fichas limpiadas el recálculo con la regla nueva diferiría más de 2 años del valor guardado. No se tocaron por instrucción.
- **Bug "Chrome ha bloqueado esta página" al abrir el perfil de José Luis Reyes Arroyo**: NO reproducible en el entorno (ficha, CV PDF y CV DOCX abren bien, sin CSP ni X-Frame-Options en las respuestas, sin navegación a data:/blob: en pestaña nueva). Pendiente: código de error exacto de Chrome y captura del usuario.
- **12 fichas sin empleos / sin años**: RESUELTO el 14-oct (re-parseadas con respaldo). Validar los datos nuevos.

### Propuestas del agente SIN APROBAR (no implementar sin OK)
- Sanear las suites antiguas estilo pytest (18 fallos + 126 errores por falta de fixtures de API/admin) para que `pytest backend/tests` quede en verde.
- Cambiar el `window.open` de "abrir ficha del duplicado" (`CandidateDetailPage.js:612`) por navegación interna: dentro del panel de vista previa (iframe) el bloqueador de pop-ups de Chrome puede cancelarlo.
- Purgar de verdad las 92 fichas sintéticas con borrado lógico y la vacante de prueba.
- Limpiar las 7 fichas de revisión manual con la regla estricta tras revisarlas una por una.
- Pasar `dedupe_experience` también al re-parseo y a la carga inicial (hoy solo corre en fusión y en el script).
- Guardar la fecha de alta de cada empleo (`added_at`) en `previous_companies` para poder auditar de dónde salió cada entrada.
- Mostrar en la ficha un aviso cuando el historial tenga el mismo empleo repetido, con botón "colapsar" manual.
- Alinear el resumen de la ficha con el del PDF (hoy la ficha todavía muestra "# Resumen Profesional Ejecutivo" con markdown crudo).
- **Años de experiencia del resto de la base**: 276 de 659 fichas cambiarían más de 2 años con la regla nueva. No recalculado por decisión del usuario.
- **Quitar el flag `single_ranking` y la ruta vieja**: solo después de 2 semanas estables en producción. No hacerlo antes.
- Revisar y fusionar manualmente las fichas marcadas como "Posible duplicado" en el ranking.


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