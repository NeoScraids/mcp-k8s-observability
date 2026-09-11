"""
Servidor MCP (Model Context Protocol) para Kubernetes y Observabilidad.
Expone herramientas especializadas para agentes autonomos de IA y Claude Desktop.
"""

import sys
import json
import asyncio
from typing import Any, Dict, List

from src.config import settings
from src.tools.k8s_tools import get_pods, get_events
from src.tools.prometheus_tools import query_prometheus
from src.tools.loki_tools import query_loki_logs
from src.models import DiagnosticReport


TOOLS_METADATA = [
    {
        "name": "get_kubernetes_pods",
        "description": "Obtiene la lista de pods en un namespace de Kubernetes con su estado de ejecucion, cantidad de reinicios y nodo asignado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace de Kubernetes a inspeccionar (por defecto 'default')",
                    "default": "default"
                }
            }
        }
    },
    {
        "name": "get_cluster_events",
        "description": "Obtiene los eventos recientes del cluster (Warnings, errores de scheduling, BackOff, OOMKilled).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace de Kubernetes a filtrar (por defecto 'default')",
                    "default": "default"
                }
            }
        }
    },
    {
        "name": "query_prometheus_metrics",
        "description": "Ejecuta una consulta PromQL en tiempo real o simulada para analizar uso de CPU, memoria, saturacion de red o latencia.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Expresion PromQL valida (ej: sum(rate(container_cpu_usage_seconds_total[5m])) by (pod))"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_loki_logs",
        "description": "Ejecuta una consulta LogQL contra Grafana Loki para recuperar trazas de logs filtradas por servicio, nivel o expresion regular.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta LogQL valida (ej: {app='payments-service'} |= 'error')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Numero maximo de lineas a recuperar",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "diagnose_pod_health",
        "description": "Herramienta compuesta SRE que correlaciona estado del pod, eventos del cluster, consumo de memoria/CPU y logs de error para emitir un diagnostico automatizado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Nombre exacto o prefijo del pod a diagnosticar"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace donde reside el pod",
                    "default": "default"
                }
            },
            "required": ["pod_name"]
        }
    }
]


def execute_tool(name: str, arguments: Dict[str, Any]) -> Any:
    """
    Despachador central de herramientas del servidor MCP.
    """
    if name == "get_kubernetes_pods":
        namespace = arguments.get("namespace", "default")
        pods = get_pods(namespace=namespace)
        return [pod.model_dump() for pod in pods]

    elif name == "get_cluster_events":
        namespace = arguments.get("namespace", "default")
        events = get_events(namespace=namespace)
        return [ev.model_dump() for ev in events]

    elif name == "query_prometheus_metrics":
        query = arguments.get("query", "up")
        result = query_prometheus(query=query)
        return result.model_dump()

    elif name == "query_loki_logs":
        query = arguments.get("query", "{}")
        limit = arguments.get("limit", 20)
        result = query_loki_logs(query=query, limit=limit)
        return result.model_dump()

    elif name == "diagnose_pod_health":
        pod_name = arguments.get("pod_name", "")
        namespace = arguments.get("namespace", "default")

        # Correlacion automatica
        pods = get_pods(namespace=namespace)
        target_pod = next((p for p in pods if pod_name in p.name), None)

        events = get_events(namespace=namespace)
        related_events = [ev.message for ev in events if pod_name in ev.involved_object or pod_name in ev.message]

        logs = query_loki_logs(query=f'{{pod="{pod_name}"}} |= "error"', limit=5)
        log_lines = [entry["line"] for entry in logs.entries]

        issues = []
        actions = []
        score = 100

        if not target_pod:
            return DiagnosticReport(
                pod_name=pod_name,
                namespace=namespace,
                status="NotFound",
                health_score=0,
                detected_issues=[f"El pod '{pod_name}' no fue encontrado en el namespace '{namespace}'."],
                recommended_actions=["Verificar nombre del pod con 'get_kubernetes_pods'"],
                recent_logs=[],
                recent_events=[]
            ).model_dump()

        if target_pod.status in ["CrashLoopBackOff", "Failed"]:
            issues.append(f"El pod esta en estado critico: {target_pod.status} con {target_pod.restarts} reinicios.")
            actions.append("Inspeccionar variables de entorno y conectividad a servicios dependientes.")
            score -= 60

        if target_pod.status == "OOMKilled" or any("OOMKilled" in ev for ev in related_events):
            issues.append("El pod fue terminado por superar el limite de memoria configurado (OOMKilled - Exit Code 137).")
            actions.append("Incrementar los limites de recursos en el Deployment (resources.limits.memory).")
            score -= 50

        if len(related_events) > 0:
            score -= (10 * len(related_events))

        score = max(0, min(100, score))

        if not actions:
            actions.append("El pod opera dentro de parametros nominales. No se requieren acciones correctivas.")

        return DiagnosticReport(
            pod_name=target_pod.name,
            namespace=namespace,
            status=target_pod.status,
            health_score=score,
            detected_issues=issues,
            recommended_actions=actions,
            recent_logs=log_lines,
            recent_events=related_events
        ).model_dump()

    else:
        raise ValueError(f"Herramienta desconocida: {name}")


def handle_json_rpc(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa solicitudes conformes a la especificacion JSON-RPC 2.0 y MCP.
    """
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "mcp-k8s-observability",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_METADATA
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            output = execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(output, indent=2, ensure_ascii=False)
                        }
                    ],
                    "isError": False
                }
            }
        except Exception as err:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error ejecutando herramienta {tool_name}: {str(err)}"
                        }
                    ],
                    "isError": True
                }
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Metodo no implementado: {method}"
            }
        }


def run_stdio_server():
    """
    Bucle principal de ejecucion stdio para Claude Desktop y clientes MCP.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            response = handle_json_rpc(req)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
