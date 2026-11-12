# Informe de solo lectura — Réplicas y estrategia de despliegue
App: Humaniq Talent Vault (deployment: atlas-recruiting-ai) — backend FastAPI
Modo: CONSULTA DE SOLO LECTURA. No se desplegó ni reinició nada.
Run activo: 73fdcebc-39e3-4fef-93db-f4ccc9adf7bb (status: success) | Cluster: target-13 | Tier: tier_0 (Starter)

## 1. Réplicas configuradas
Fuente: get_tier
- replicas (deseadas): **2**
- max_replicas: **2**
- Es decir, el conteo está fijo en 2 (min = max = 2).

## 2. Autoescalado
Fuente: get_tier
- hpa_enabled: **false** (sin Horizontal Pod Autoscaler)
- vpa_enabled: **false** (sin Vertical Pod Autoscaler)
- Conclusión: **NO hay autoescalado**. Siempre corren 2 réplicas, sin escalar por carga.

Recursos por pod (tier_0 Starter): CPU request 50m / limit 250m; Memoria request 200Mi / limit 512Mi; ephemeral-storage 1Gi.

## 3. Pods actualmente en ejecución
Fuente: get_pod_events (run activo)
- Pods confirmados en estado Running + Ready: **1** (r-73fdcebc-...-5hkgn, restart_count 0, arrancado 2026-11-09T16:47:49Z).
- IMPORTANTE / limitación de la herramienta: get_pod_events es una herramienta basada en eventos y NO enumera de forma fiable TODAS las réplicas vivas (los eventos de K8s se recolectan tras ~1h; la ventana no mostró eventos recientes). El conteo DESEADO/configurado es 2. No puedo afirmar con certeza desde esta herramienta que ambos pods estén arriba en este instante, pero la configuración pide 2 y no hubo kills/OOM registrados (kill_findings vacío).

## 4. Estrategia de despliegue (qué hace un deploy)
La plataforma NO hace un RollingUpdate in-place ni un Recreate sobre el mismo objeto Deployment. Usa un modelo **blue/green por run**:
- Cada deploy crea un conjunto de pods NUEVO con nombre propio del run (Deployment + Service nuevos), usando la imagen recién construida.
- Los pods nuevos arrancan y deben pasar readiness + health_check **mientras los pods viejos siguen vivos y sirviendo tráfico**.
- En el paso `promote` se hace un **switch atómico** de tráfico del run viejo al nuevo; los pods viejos se limpian DESPUÉS del switch.
- Resultado: despliegue sin downtime; sí existe una ventana de solapamiento en la que conviven la versión vieja y la nueva (hasta 2 viejos + 2 nuevos = 4 pods backend simultáneos de dos versiones).

## 5. Implicaciones para "reanudación segura de cargas de CV al arranque" con >1 réplica
- En estado estable corren **2 réplicas idénticas en paralelo**. Cualquier lógica de "reanudar cargas al arranque" se ejecutará en CADA pod → se necesita coordinación entre réplicas (leader election / lock distribuido / idempotencia) para que las 2 no tomen el mismo trabajo.
- Durante un deploy el solapamiento blue/green eleva la contención: los 2 pods viejos Y los 2 pods nuevos pueden estar vivos a la vez, cada uno disparando su lógica de arranque. El diseño debe ser seguro ante hasta 4 arranques concurrentes, no solo 2.

## Resumen
- Réplicas configuradas: 2 (fijas, min=max=2).
- Autoescalado: ninguno (HPA y VPA deshabilitados).
- Pods en ejecución: 1 confirmado por la herramienta de eventos (deseado=2; la herramienta no enumera fiablemente todas las réplicas).
- Estrategia: blue/green por run con switch atómico en promote (los pods nuevos arrancan mientras los viejos siguen vivos; no es RollingUpdate in-place ni Recreate), sin downtime.
