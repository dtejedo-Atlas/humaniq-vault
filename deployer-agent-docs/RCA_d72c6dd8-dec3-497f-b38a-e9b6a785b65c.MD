# RCA — atlas-recruiting-ai redeploy failure (run d72c6dd8-dec3-497f-b38a-e9b6a785b65c)

## Symptom
- Envelope: `failed_step: deploy_k8s` / "deployment failed to become ready: timed out waiting for the condition".
- nginx logged repeated `connect() failed (111: Connection refused)` to `http://127.0.0.1:8001/health`, then `Backend died, shutting down nginx...`.
- The K8s "deploy timeout" is a downstream symptom — the real failure is the **backend process crashing on startup**, so the pod never became ready and health checks never passed.

## Root cause (verified)
The FastAPI backend crashes during import:
```
RuntimeError: CORS_ORIGINS contiene un origen no válido; no se permiten comodines con credenciales
  File "/app/backend/cors_config.py", line 15, in get_cors_origins
  File "/app/backend/server.py", line 6116, in <module>
    allow_origins=get_cors_origins(),
```
MongoDB connected fine (`[STARTUP] Connected to MongoDB Atlas`); the crash is purely the CORS config validation.

`backend/cors_config.py` `get_cors_origins()` is intentionally fail-closed: it reads `os.environ['CORS_ORIGINS']`, splits on commas, and rejects the whole set if ANY origin contains `*`, lacks an http/https scheme, or carries a path/query/userinfo — because `allow_credentials=True` (server.py line ~6113) forbids wildcard origins.

The value being validated is the **production `CORS_ORIGINS` deployment secret**, which is invalid:
- The preview `backend/.env` value is CLEAN and valid: `https://atlas-recruiting-ai.emergent.host,https://atlas-recruiting-ai.preview.emergentagent.com`.
- `list_secrets` (equals-check against that clean value) returned `CORS_ORIGINS matches_expected: false` — the stored production value DIFFERS from the valid preview value and contains a wildcard/malformed origin that trips the validator.
- On redeploy, pre-existing production secret values are NOT overwritten by preview `.env`, so the stale/bad production value persisted and the newer `cors_config.py` validation now rejects it.

## Why this is not a manifest or source-code bug
- Build succeeded; manifests are not implicated.
- `cors_config.py` behaves as designed (security fail-closed). No code change is required.
- The eph sandbox has no production secrets injected, so this exact crash cannot be reproduced there — diagnosis is from the failing run's logs + a secret equals-comparison, not an in-pod repro.

## Fix (User — Secrets)
Update the production `CORS_ORIGINS` secret in **Deployment Panel → Secrets** to a comma-separated list of explicit, credentialed-safe origins with NO wildcards, e.g.:
```
https://atlas-recruiting-ai.emergent.host,https://atlas-recruiting-ai.preview.emergentagent.com
```
Rules the value must satisfy (per cors_config.py): each entry must be `http(s)://host[:port]` only — no `*`, no trailing path/query/fragment, no user:pass. Save, then redeploy. Re-running the pipeline without changing this secret will fail identically.

## Note
`CORS_PREVIEW_PUBLIC_ORIGIN` / `CORS_PREVIEW_PROXY_ORIGIN` exist in preview `.env` but are absent from the production secret store; since `PreviewAwareCORSMiddleware` reads both via optional `os.environ.get` and both are unset, that path is skipped and is not the cause.
