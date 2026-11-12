# Consulta de solo lectura — Humaniq Talent Vault (atlas-recruiting-ai)

Modo: SOLO LECTURA. No se desplegó, reinició ni modificó nada.

## Contexto
- Deployment: atlas-recruiting-ai (backend FastAPI, frontend Cloudflare)
- Run activo (sirviendo tráfico hoy y base del próximo redeploy): `73fdcebc-39e3-4fef-93db-f4ccc9adf7bb` (type=redeploy, success)
- URL: https://atlas-recruiting-ai.emergent.host (+ dominio vault.humaniq.com.mx)

## (1) ¿Existe UPLOAD_WORKERS_ENABLED en producción?
NO. `list_secrets` sobre el run activo devuelve 22 claves y **UPLOAD_WORKERS_ENABLED NO está entre ellas**. La comparación con `equals` tampoco produjo coincidencia.
- Las claves presentes: ATLAS_DB_NAME, ATLAS_URI, CORS_ORIGINS, CORS_PREVIEW_PROXY_ORIGIN, CORS_PREVIEW_PUBLIC_ORIGIN, DB_NAME, EMERGENT_LLM_KEY, ENABLE_HEALTH_CHECK, HUMANIQ_CORS_ORIGINS, INTEGRATION_PROXY_URL, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, JWT_SECRET_KEY, MATCHING_ENGINE_VERSION, MONGO_URL, OPENAI_API_KEY, PUBLIC_APP_URL, REACT_APP_BACKEND_URL, RESEND_API_KEY, SENDER_EMAIL, WDS_SOCKET_PORT, WEBHOOK_CRON_SECRET.
- El entorno de los pods del run activo = exactamente ese conjunto de claves. Por tanto la bandera **no existe en los pods actuales** ni en el set de secretos que heredará el próximo deploy. No tiene valor ("true" ni "false"); simplemente está ausente.

## (2) ¿De dónde toma producción las variables de ambiente?
Dos clases de claves con reglas distintas:
- **Claves de SISTEMA** (MONGO_URL, DB_NAME, REACT_APP_BACKEND_URL, INTEGRATION_PROXY_URL, STRIPE_*, EMERGENT_PUSH_KEY): se regeneran desde el estado de producción en CADA deploy y siempre sobrescriben cualquier valor de preview.
- **Claves personalizadas (del usuario)**: 
  - Primer deploy (initial): se siembran desde backend/.env del preview.
  - Cada deploy posterior (redeploy — este es el caso): se arrastran desde el run de PRODUCCIÓN anterior. El valor editado en Deployment Panel → Secrets gana. El backend/.env de preview SOLO AGREGA claves nuevas; nunca sobrescribe una clave ya existente en producción.

Prioridad en producción (de mayor a menor): **Deployment Panel → Secrets (slot live)** > valor arrastrado del run de producción previo > backend/.env de preview (y éste último solo aplica para claves totalmente nuevas).

## (3) ¿Una línea nueva en /app/backend/.env de preview llega a los pods de prod?
SÍ, en el caso de UPLOAD_WORKERS_ENABLED. Como esa clave NO existe hoy en producción, en el próximo redeploy el backend/.env de preview la tratará como clave nueva y la AGREGARÁ al entorno de los pods de producción con el valor que tenga en el .env (p.ej. false). El hecho de estar en .gitignore es irrelevante: pull_source copia el /app del pod de preview, no el repositorio git.

### Implicación para el objetivo "dejar la bandera en false solo en preview"
Poner `UPLOAD_WORKERS_ENABLED=false` en backend/.env de preview NO la mantiene aislada en preview: se propagará a producción en el siguiente deploy. Para lograr que quede false únicamente en preview, dos opciones del lado del usuario:
- Definir explícitamente UPLOAD_WORKERS_ENABLED en Deployment Panel → Secrets con el valor que se desee en producción (p.ej. "true"). Al existir ya en prod, el .env de preview no podrá sobrescribirla, y localmente en preview seguirá valiendo false. 
- O no colocarla en backend/.env y manejar el flag en preview por un medio que no se incluya en pull_source.

Evidencia: describe_deployment_state (run activo 73fdcebc…, redeploy, frontend cloudflare) + list_secrets (22 claves, sin UPLOAD_WORKERS_ENABLED).
