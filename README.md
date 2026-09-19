# mcp-k8s-observability

Servidor [MCP](https://modelcontextprotocol.io/) en Python que conecta agentes de IA (Claude Desktop, Cursor, etc.) con la infraestructura de Kubernetes y el stack de observabilidad.

La idea es simple: en vez de copiar y pegar outputs de `kubectl` y `curl` en el chat, el agente puede llamar directamente a las herramientas y obtener el estado de los pods, hacer queries a Prometheus y buscar logs en Loki.

## Que hace

El servidor expone 8 herramientas via JSON-RPC (transporte stdio):

**Kubernetes**
- **`list_namespaces`** - Lista namespaces con estado y fecha de creacion (punto de entrada natural)
- **`get_kubernetes_pods`** - Pods con su estado, reinicios y nodo asignado
- **`get_cluster_events`** - Eventos del cluster (BackOff, OOMKilled, FailedScheduling)
- **`get_pod_logs`** - Ultimas N lineas de log via la API de K8s (`kubectl logs --tail`), con soporte `--previous`

**Observabilidad**
- **`query_prometheus_metrics`** - PromQL instant query
- **`query_prometheus_range`** - PromQL range query con ventana y resolucion configurable (analisis de tendencias)
- **`query_loki_logs`** - LogQL contra Grafana Loki

**Diagnostico**
- **`diagnose_pod_health`** - Herramienta compuesta: cruza estado del pod + metricas + eventos + logs y saca un health score (0-100) con acciones sugeridas. Detecta CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff y pods con alto ratio de reinicios

## Modo mock

Todo funciona sin cluster real. Con `MCP_MODE=mock` genera datos sinteticos que simulan pods en CrashLoopBackOff, OOMKilled, etc. Incluye logs mock realistas (stack traces de Java OOM, latencias de transacciones, probes de health check). Util para probar prompts y ver como reacciona el agente sin necesidad de tener infraestructura activa.

## Como probarlo

```bash
git clone https://github.com/NeoScraids/mcp-k8s-observability.git
cd mcp-k8s-observability

# Con make
make setup
make test

# O manual
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python test_client.py
```

La salida muestra el handshake MCP, la lista de herramientas, pods, logs del pod anterior y un diagnostico automatico de un pod simulado con OOMKilled.

## Conectar con Claude Desktop

Agregar en `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "k8s-observability": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/ruta/a/mcp-k8s-observability",
      "env": { "MCP_MODE": "mock" }
    }
  }
}
```

## Estructura

```
src/
  config.py              # Variables de entorno y settings
  models.py              # Esquemas Pydantic
  server.py              # Loop stdio + despachador JSON-RPC
  tools/
    k8s_tools.py         # Pods, eventos, namespaces y logs (live o mock)
    prometheus_tools.py  # Queries PromQL (instant y range)
    loki_tools.py        # Queries LogQL
test_client.py           # Prueba rapida sin cliente externo
Makefile                 # setup, test, lint, docker-build
Dockerfile               # Multi-stage, 70MB aprox
```

## Por que existe esto

En el trabajo uso herramientas similares para no tener que estar saltando entre terminales, Grafana y Slack cuando llega una alerta. Este repo es una version limpia de esa idea, sin datos corporativos, que cualquiera puede clonar y adaptar.

## Licencia

MIT
