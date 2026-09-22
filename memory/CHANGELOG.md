# CHANGELOG - Humaniq Talent Vault

## 2026-09-22 — Baja de Patricia Sáez
- Cuenta `psaez@humaniq.com.mx` (`bb8ac7a2-ba5b-4312-9baa-f2bbf973f4bc`) desactivada mediante la API existente: `is_active: false`, HTTP 200; cuenta conservada y excluida de usuarios activos.
- Sin cambios en código, contraseña, candidatos, notas o asignaciones. En el documento de usuario expuesto por API solo cambiaron `is_active` y `updated_at`.
- Verificado HTTP 403 `Cuenta desactivada` en `/api/auth/me` con JWT de comprobación válido, efímero y no persistido.
- Login con contraseña desconocida/aleatoria: HTTP 401. Login con contraseña correcta NO probado porque no está disponible; la implementación verifica contraseña antes de devolver 403 por estado inactivo. No afirmar que se verificó 403 en `/api/auth/login`.
- Comparación literal de candidatos no concluyente por valores `classified_at` generados por el modelo en cada respuesta; diferencia reproducida con GET consecutivos, sin modificar datos.
- PRD dividido para mantenerlo conciso; historial anterior completo en `CHANGELOG_LEGACY.md`, pendientes en `ROADMAP.md`.

## 2026-07-16 — Limpieza de cuentas Atlas + hardening `is_active`

### Cuentas
- Desactivadas 6 cuentas de prueba (`is_active: False`, historial preservado):
  test_user_011349, test_user_011402, test_user_b3fc4cd1, test_user_a7068b0c,
  test_user_fa5b2128, recruiter_test @atlas.com
- Desactivadas 4 cuentas viejas @atlas.com reemplazadas por invitaciones a
  humaniq.com.mx / hqts.com.mx: patricia, ximena, alejandra, viridiana
- Rotada la contraseña de `test_utf8@atlas.com`; guardada únicamente en
  `/app/memory/test_credentials.md` (password anterior invalidada).
- `test_utf8` marcado explícitamente `is_active: True`.

### Seguridad (fix crítico)
- `POST /api/auth/login`: ahora responde **403 "Cuenta desactivada"** cuando
  `is_active === False` (antes emitía JWT válido).
- `get_current_user`: mismo bloqueo → tokens vivos de usuarios desactivados
  quedan invalidados en la siguiente request.
- Verificado con curl real: patricia@atlas.com → 403; test_utf8 (nueva pwd) → 200; dtejedo → 200.

### Scripts (nuevos, en `/app/backend/scripts/`)
- `list_all_users.py` — dump con rol/is_active/last_login
- `deactivate_and_rotate.py` — desactiva por email + rota password (usa `db_connection.py`)

### Estado final de cuentas activas (10)
| Email | Rol |
|-------|-----|
| dtejedo@gmail.com | super_admin |
| superadmin@atlas.com | super_admin |
| test_utf8@atlas.com | admin |
| diego@humaniq.com.mx | admin |
| psaez@humaniq.com.mx | recruiter |
| xsanchez@humaniq.com.mx | recruiter |
| majo@humaniq.com.mx | recruiter |
| arosas@hqts.com.mx | recruiter |
| brangel@hqts.com.mx | recruiter |
| vguerrero@hqts.com.mx | recruiter |

**Adicional 2026-07-16:** `admin@atlas.com` también desactivada (cuenta huérfana de pruebas de marzo).
