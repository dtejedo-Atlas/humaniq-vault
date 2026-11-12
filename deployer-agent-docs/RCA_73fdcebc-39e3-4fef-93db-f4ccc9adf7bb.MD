# Read-only consultation — UPLOAD_WORKERS_ENABLED (Humaniq Talent Vault / atlas-recruiting-ai)

Mode: READ-ONLY. No pipeline run, no restart, no secret/manifest change.
Deployment: atlas-recruiting-ai | active (serving) run: 73fdcebc-39e3-4fef-93db-f4ccc9adf7bb
frontend_type: cloudflare | tier_0 | URL: https://atlas-recruiting-ai.emergent.host

## What the user asked
After editing UPLOAD_WORKERS_ENABLED in the Secrets panel (preview/test=false, production/live=true), confirm with production data:
1. Does UPLOAD_WORKERS_ENABLED already exist in the secret set the NEXT production deploy will use (live slot / pending-to-publish), and with what exact value?
2. Do the CURRENT production pods have it, or is it absent until publish?
3. If the baked backend/.env does NOT contain the key and the live slot = "true", will the next deploy's pods read "true"?

## Evidence

### (2) Current production pods — ABSENT (verified)
list_secrets on the ACTIVE/serving run 73fdcebc returns the full custom+system key set:
ATLAS_DB_NAME, ATLAS_URI, CORS_ORIGINS, CORS_PREVIEW_PROXY_ORIGIN, CORS_PREVIEW_PUBLIC_ORIGIN, DB_NAME, EMERGENT_LLM_KEY, ENABLE_HEALTH_CHECK, HUMANIQ_CORS_ORIGINS, INTEGRATION_PROXY_URL, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, JWT_SECRET_KEY, MATCHING_ENGINE_VERSION, MONGO_URL, OPENAI_API_KEY, PUBLIC_APP_URL, REACT_APP_BACKEND_URL, RESEND_API_KEY, SENDER_EMAIL, WDS_SOCKET_PORT, WEBHOOK_CRON_SECRET.
UPLOAD_WORKERS_ENABLED is NOT in this set. => The currently-running production pods do NOT have the variable.

### (1) Next-deploy / live slot — UNVERIFIABLE with production tooling
list_secrets reads ONLY the active (currently serving) run. There is no tool that reads the pending/staged "live slot" that the user just edited in the Secrets tab. Therefore I cannot confirm with production data the exact staged value.
By the platform secrets model (custom keys are carried forward from the prior prod run and a value the user set in the Secrets tab wins), the EXPECTED value composed into the next run at the write_secrets step is "true" — but this is model-based inference, not a direct read. Reported as UNVERIFIED.

### (3) Baked .env + env precedence — verified in isolated eph sandbox (run 73fdcebc source)
- `cat backend/.env` (full contents): keys present are MONGO_URL, DB_NAME, CORS_ORIGINS, HUMANIQ_CORS_ORIGINS, WEBHOOK_CRON_SECRET, CORS_PREVIEW_PUBLIC_ORIGIN, CORS_PREVIEW_PROXY_ORIGIN, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, ATLAS_URI, ATLAS_DB_NAME, MATCHING_ENGINE_VERSION, RESEND_API_KEY, SENDER_EMAIL, PUBLIC_APP_URL. UPLOAD_WORKERS_ENABLED is NOT present in the baked .env.
- server.py:82 = `load_dotenv(ROOT_DIR / '.env')` with NO override arg => python-dotenv default override=False, so OS/pod environment variables take precedence over .env values.
- The platform injects custom secrets as real pod environment variables.
=> If the live slot holds "true" at the next deploy, the pod environment will carry UPLOAD_WORKERS_ENABLED=true and os.getenv("UPLOAD_WORKERS_ENABLED") would return "true". Because .env does not define the key, there is no conflict regardless of override behavior. Answer to (3): YES, at the environment level the pods would read "true".

### CRITICAL caveat — the flag is currently INERT in code
grep for `UPLOAD_WORKERS_ENABLED` across the backend source (excluding tests) returns ZERO matches. No production code path reads this variable today. So even though the env var would be present and equal "true" after publishing, setting it has NO functional effect until backend code is added that actually reads os.getenv("UPLOAD_WORKERS_ENABLED").

## Bottom line
- Current prod pods: variable ABSENT (verified).
- Next-deploy live-slot value: cannot be read directly (no tool for the pending slot); expected "true" by the secrets model — UNVERIFIED.
- Will next pods read "true" if live=true: YES at the env level (baked .env lacks the key, pod env wins, load_dotenv override=False).
- But: no backend code reads the flag, so it has no effect until code consumes it.
