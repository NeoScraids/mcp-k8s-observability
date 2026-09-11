# mcp-k8s-observability

Servidor [MCP](https://modelcontextprotocol.io/) en Python que conecta agentes de IA (Claude Desktop, Cursor, etc.) con la infraestructura de Kubernetes y el stack de observabilidad.

La idea es simple: en vez de copiar y pegar outputs de `kubectl` y `curl` en el chat, el agente puede llamar directamente a las herramientas y obtener el estado de los pods, hacer queries a Prometheus y buscar logs en Loki.

## Que hace

El servidor expone 5 herramientas via JSON-RPC (transporte stdio):

- **`get_kubernetes_pods`** - Lista pods con su estado, reinicios y nodo asignado
- **`get_cluster_events`** - Eventos del cluster (BackOff, OOMKilled, FailedScheduling)
- **`query_prometheus_metrics`** - Ejecuta PromQL contra Prometheus
- **`query_loki_logs`** - Ejecuta LogQL contra Loki
- **`diagnose_pod_health`** - Herramienta compuesta: cruza estado del pod + metricas + eventos + logs y saca una puntuacion de salud (0-100) con acciones sugeridas

## Modo mock

Todo funciona sin cluster real. Con `MCP_MODE=mock` genera datos sinteticos que simulan pods en CrashLoopBackOff, OOMKilled, etc. Util para probar prompts y ver como reacciona el agente sin necesidad de tener infraestructura activa.

## Como probarlo

```bash
git clone https://github.com/NeoScraids/mcp-k8s-observability.git
cd mcp-k8s-observability
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Correr el cliente de prueba
python test_client.py
```

La salida muestra el handshake MCP, la lista de herramientas y un diagnostico automatico de un pod simulado con OOMKilled.

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
  config.py          # Variables de entorno y settings
  models.py          # Esquemas Pydantic
  server.py          # Loop stdio + despachador JSON-RPC
  tools/
    k8s_tools.py     # Pods y eventos (live con kubernetes-client o mock)
    prometheus_tools.py  # Queries PromQL
    loki_tools.py    # Queries LogQL
test_client.py       # Prueba rapida sin cliente externo
Dockerfile           # Multi-stage, 70MB aprox
```

## Por que existe esto

En el trabajo uso herramientas similares para no tener que estar saltando entre terminales, Grafana y Slack cuando llega una alerta. Este repo es una version limpia de esa idea, sin datos corporativos, que cualquiera puede clonar y adaptar.

## Licencia

MIT
