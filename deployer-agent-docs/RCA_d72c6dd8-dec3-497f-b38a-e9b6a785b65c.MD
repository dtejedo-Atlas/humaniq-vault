# RCA — atlas-recruiting-ai (Humaniq Talent Vault) — deploy fallido d72c6dd8

## Veredicto
Fallo de arranque del backend por un **secreto de producción obsoleto**: `CORS_ORIGINS` está guardado en el store de secretos con el valor **`*`** (comodín). `cors_config.py` es fail-closed y aborta en la línea 15 ("no se permiten comodines con credenciales"). El backend muere en el import → nginx da `connection refused` en `127.0.0.1:8001/health` → el health check nunca pasa → `deployment failed to become ready` (timeout). El run fallido nunca se promovió; sigue en vivo el run exitoso de julio (`40c45d80`).

**NO es un problema de código.** `cors_config.py` funciona por diseño y el `backend/.env` del preview está limpio (sin comodines). El problema es puramente de configuración de secretos en producción.

## Evidencia
- Traceback del pod fallido: `RuntimeError: CORS_ORIGINS contiene un origen no válido; no se permiten comodines con credenciales`, en `cors_config.py:15` (la comprobación de comodín, ANTES de la línea 25). Precedido de `[STARTUP] Connected to MongoDB Atlas - Database: atlas_talent_vault` → Mongo conecta bien; el único fallo es CORS.
- `list_secrets` (run activo/en vivo 40c45d80) con comparación `equals`:
  - `CORS_ORIGINS`: existe, `is_empty=false`. `matches_expected=false` contra el valor limpio del .env; `matches_expected=TRUE` contra `"*"`. → **El valor guardado es exactamente `*`.**
  - `CORS_PREVIEW_PROXY_ORIGIN` y `CORS_PREVIEW_PUBLIC_ORIGIN`: **NO aparecen** en el store del run en vivo → son claves nuevas añadidas en preview, aún no promovidas ("Añadido, no está en vivo aún").

## Respuestas a las 3 preguntas

### 1) ¿Existe CORS_ORIGINS en producción? ¿Valor? ¿Fuente?
Sí, existe como **secreto guardado** en producción. Valor = `*` (comodín), NO coincide con el .env limpio. **Fuente: secreto persistido de un deploy anterior**, no el `backend/.env` que viaja con el código (ese está limpio) ni inyección de plataforma. Regla clave: en un redeploy los valores de secretos **preexistentes NO se sobrescriben**, por eso tu `.env` limpio nunca reemplazó el `*` guardado. Esto es el bloqueante (línea 15).

Nota importante: aunque el panel "no te muestre" CORS_ORIGINS, el store de secretos **sí lo contiene** (confirmado por metadata). Hay que buscarlo/editarlo en la pestaña Secretos.

### 2) ¿Existen los dos CORS_PREVIEW_* en producción? ¿En vivo o pendientes?
En el run en vivo NO existen todavía. Coinciden con lo que ves en el panel: **añadidos en preview, pendientes** — solo pasan a estar en vivo en el próximo deploy exitoso. No son la causa del crash: el backend murió en la línea 15 (comodín) antes de llegar a la comprobación de la línea 25 (par preview presente/ausente + subconjunto). Con el par presente y el valor limpio, la línea 25 pasará (`CORS_PREVIEW_PUBLIC_ORIGIN` está incluido en el CORS_ORIGINS limpio).

### 3) Acciones exactas en el panel de Secretos
1. **Editar** el secreto `CORS_ORIGINS` (pestaña Secretos → editar valor). Cambiar `*` por el valor exacto:
   `https://atlas-recruiting-ai.emergent.host,https://atlas-recruiting-ai.preview.emergentagent.com`
   (Un redeploy por sí solo NO lo arregla: los secretos preexistentes no se sobrescriben; hay que editarlo en la UI.)
2. `CORS_PREVIEW_PROXY_ORIGIN` y `CORS_PREVIEW_PUBLIC_ORIGIN`: no requieren acción en la UI (no se pueden añadir desde ahí). Ya están añadidos en preview y se promoverán solos en el próximo deploy. Verifica que sus valores sean:
   - `CORS_PREVIEW_PUBLIC_ORIGIN` = `https://atlas-recruiting-ai.preview.emergentagent.com`
   - `CORS_PREVIEW_PROXY_ORIGIN` = `https://atlas-recruiting-ai.cluster-2.preview.emergentcf.cloud`
3. Nada que eliminar. Guardar el cambio de `CORS_ORIGINS` y **redesplegar**. Tras el deploy: línea 15 pasa (sin comodín), línea 25 pasa (par presente + subconjunto correcto) → el backend arranca.

## Alcance / cautela
`list_secrets` solo lee el run en vivo (`40c45d80`, julio), no el run fallido `d72c6dd8`. Pero `CORS_ORIGINS` es un secreto persistente que se arrastra sin cambios a cada run (no se sobrescribe), por lo que el `*` observado es el mismo valor que recibió el pod fallido. Inferencia bien fundamentada, coherente con el traceback (línea 15 = comodín).
