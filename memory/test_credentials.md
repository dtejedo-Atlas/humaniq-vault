# Test Credentials for Humaniq Talent Vault

## Admin User (testing) — ÚNICA fuente de verdad
- **Email:** test_utf8@atlas.com
- **Password:** AdzIzO9zalvsE07tW+q#
- **Role:** admin
- **Rotated:** 2026-07-16 (rotación de seguridad; password anterior invalidada)

## Real Users (activos, contraseña temporal 2026-06-03)
- dtejedo@gmail.com / Humaniq2026! (super_admin, dueño)
- superadmin@atlas.com / Humaniq2026! (super_admin)
- diego@humaniq.com.mx (admin, invitación — sin password fija en este doc)
- psaez@humaniq.com.mx (recruiter — invitación)
- xsanchez@humaniq.com.mx (recruiter — invitación)
- majo@humaniq.com.mx (recruiter — invitación)
- arosas@hqts.com.mx (recruiter — invitación)
- brangel@hqts.com.mx (recruiter — invitación)
- vguerrero@hqts.com.mx (recruiter — invitación)

## Cuentas desactivadas (is_active=False) — NO usar para pruebas
- test_user_011349@atlas.com, test_user_011402@atlas.com, test_user_b3fc4cd1@atlas.com,
  test_user_a7068b0c@atlas.com, test_user_fa5b2128@atlas.com, recruiter_test@atlas.com
- patricia@atlas.com, ximena@atlas.com, alejandra@atlas.com, viridiana@atlas.com
  (reemplazadas por invitaciones a humaniq.com.mx / hqts.com.mx)
- admin@atlas.com (huérfana de pruebas de marzo 2026)

## API Base URL
- **Preview:** https://atlas-recruiting-ai.preview.emergentagent.com
- **Production:** https://atlas-recruiting-ai.emergent.host
- **API Prefix:** /api

## Authentication
- **Endpoint:** POST /api/auth/login
- **Body:** `{"email": "...", "password": "..."}`
- **Response:** `{"access_token": "...", "token_type": "bearer"}`
- **Header:** `Authorization: Bearer {access_token}`
- Nota: users collection guarda hash en `password_hash`.
- Login/`get_current_user` bloquean cuentas con `is_active: False` (403 "Cuenta desactivada").

## Last Updated
- Date: 2026-07-16
- Updated by: E1 Agent (limpieza Atlas + rotación test_utf8 + fix is_active en login)

## Google OAuth (Emergent-managed)
- Solo emails registrados en `users` con `is_active != False` pueden entrar.
- No hay contraseñas para el flujo Google. El endpoint emite el mismo JWT que el login normal.

## Invitaciones y contraseñas (Resend)
- RESEND_API_KEY en backend/.env (modo prueba: dominio pendiente de verificación)
- SENDER_EMAIL=onboarding@resend.dev (cambiar a diego@humaniq.com.mx tras verificar dominio)
- Tokens de invitación/reset: colección `password_tokens` (sha256, un solo uso, 48h)
- Suite: /app/backend/tests/test_invitation_password_flow.py
