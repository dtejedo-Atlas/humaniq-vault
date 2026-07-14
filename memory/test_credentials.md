# Test Credentials for Humaniq Talent Vault

## Admin User (testing)
- **Email:** test_utf8@atlas.com
- **Password:** Humaniq123
- **Role:** admin

## Real Users (password reset 2026-06-03, temp password)
- dtejedo@gmail.com / Humaniq2026! (recruiter, owner)
- superadmin@atlas.com / Humaniq2026! (super_admin)
- patricia@atlas.com / Humaniq2026! (recruiter)
- ximena@atlas.com / Humaniq2026! (recruiter)
- alejandra@atlas.com / Humaniq2026! (recruiter)
- viridiana@atlas.com / Humaniq2026! (recruiter)

## API Base URL
- **Preview:** https://atlas-recruiting-ai.preview.emergentagent.com
- **Production:** https://atlas-recruiting-ai.emergent.host
- **API Prefix:** /api

## Authentication
- **Endpoint:** POST /api/auth/login
- **Body:** `{"email": "...", "password": "..."}`
- **Response:** `{"access_token": "...", "token_type": "bearer"}`
- **Header:** `Authorization: Bearer {access_token}`
- Note: users collection stores hash in `password_hash` field (NOT `hashed_password`)

## Last Updated
- Date: 2026-06-03
- Updated by: E1 Agent

## Google OAuth (Emergent-managed)
- Solo emails YA registrados en la colección `users` pueden entrar con Google (403 si no existen).
- Cuentas vinculables para prueba manual: dtejedo@gmail.com (rol existente en users).
- No hay contraseñas para el flujo Google (OAuth). El endpoint emite el mismo JWT que el login normal.

## Invitaciones y contraseñas (Resend)
- RESEND_API_KEY en backend/.env (modo prueba: solo envía a diego@humaniq.com.mx hasta verificar dominio humaniq.com.mx)
- SENDER_EMAIL=onboarding@resend.dev (cambiar a diego@humaniq.com.mx tras verificar dominio)
- Tokens de invitación/reset: colección password_tokens (sha256, un solo uso, 48h). Para generar uno en claro en tests: invitation_service.create_token(db, user_id, purpose, admin_id)
- Suite: /app/backend/tests/test_invitation_password_flow.py
