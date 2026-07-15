# CHANGELOG - Humaniq Talent Vault

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
