# Test Credentials for Humaniq Talent Vault

## Admin User
- **Email:** test_utf8@atlas.com
- **Password:** Humaniq123
- **Role:** admin

## API Base URL
- **Preview:** https://atlas-recruiting-ai.preview.emergentagent.com
- **API Prefix:** /api

## Authentication
- **Endpoint:** POST /api/auth/login
- **Body:** `{"email": "test_utf8@atlas.com", "password": "Humaniq123"}`
- **Response:** `{"access_token": "...", "token_type": "bearer"}`
- **Header:** `Authorization: Bearer {access_token}`

## Last Updated
- Date: 2025-12-30
- Updated by: E1 Agent
