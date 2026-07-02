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
