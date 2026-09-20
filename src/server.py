"""
Servidor MCP (Model Context Protocol) para Kubernetes y Observabilidad.
Expone herramientas especializadas para agentes autonomos de IA y Claude Desktop.
"""

import sys
import json
import asyncio
from typing import Any, Dict, List

from src.config import settings
from src.tools.k8s_tools import (
    get_pods,
    get_events,
    list_namespaces,
    get_pod_logs,
    get_pod_detail,
    get_cluster_nodes,
)
from src.tools.prometheus_tools import query_prometheus, query_prometheus_range
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
    },
    {
        "name": "list_namespaces",
        "description": "Lista todos los namespaces del cluster con su estado (Active/Terminating) y fecha de creacion. Recomendado como primer paso antes de consultar pods o eventos, para no adivinar nombres.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "query_prometheus_range",
        "description": "Ejecuta una consulta PromQL sobre un rango de tiempo (matrix). Devuelve datapoints con resolucion configurable. Util para analizar tendencias de CPU, memoria o latencia antes de un incidente.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Expresion PromQL valida"
                },
                "range_minutes": {
                    "type": "integer",
                    "description": "Ventana de tiempo en minutos hacia atras desde ahora (default: 15)",
                    "default": 15
                },
                "step_seconds": {
                    "type": "integer",
                    "description": "Resolucion entre puntos de datos en segundos (default: 60)",
                    "default": 60
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_pod_logs",
        "description": "Obtiene las ultimas N lineas de log de un pod directamente via la API de Kubernetes (sin depender de Loki). Equivalente a 'kubectl logs --tail'. Soporta --previous para ver logs de la instancia anterior al ultimo reinicio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Nombre exacto del pod"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace del pod",
                    "default": "default"
                },
                "tail_lines": {
                    "type": "integer",
                    "description": "Cantidad de lineas desde el final (default: 50)",
                    "default": 50
                },
                "container": {
                    "type": "string",
                    "description": "Nombre del contenedor si el pod tiene mas de uno (dejar vacio para el primero)",
                    "default": ""
                },
                "previous": {
                    "type": "boolean",
                    "description": "Si es true, retorna logs de la instancia anterior al ultimo reinicio",
                    "default": false
                }
            },
            "required": ["pod_name"]
        }
    },
    {
        "name": "get_pod_detail",
        "description": "Obtiene la configuracion y estado detallado de un pod: contenedores, imagenes, exit codes, limits/requests y condiciones.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Nombre exacto o prefijo del pod"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace del pod",
                    "default": "default"
                }
            },
            "required": ["pod_name"]
        }
    },
    {
        "name": "get_cluster_nodes",
        "description": "Lista los nodos del cluster con su estado (Ready/NotReady), roles, capacidad y condiciones de presion (memoria/disco).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def execute_tool(name: str, arguments: Dict[str, Any]) -> Any:
    """Despachador central de herramientas del servidor MCP."""
    if name == "get_kubernetes_pods":
        namespace = arguments.get("namespace", "default")
        pods = get_pods(namespace=namespace)
        return [pod.model_dump() for pod in pods]

    elif name == "get_cluster_events":
        namespace = arguments.get("namespace", "default")
        events = get_events(namespace=namespace)
        return [ev.model_dump() for ev in events]

    elif name == "list_namespaces":
        return list_namespaces()

    elif name == "get_cluster_nodes":
        return get_cluster_nodes()

    elif name == "get_pod_detail":
        return get_pod_detail(
            pod_name=arguments.get("pod_name", ""),
            namespace=arguments.get("namespace", "default"),
        )

    elif name == "query_prometheus_metrics":
        query = arguments.get("query", "up")
        result = query_prometheus(query=query)
        return result.model_dump()

    elif name == "query_prometheus_range":
        query = arguments.get("query", "up")
        range_min = arguments.get("range_minutes", 15)
        step = arguments.get("step_seconds", 60)
        result = query_prometheus_range(query=query, range_minutes=range_min, step_seconds=step)
        return result.model_dump()

    elif name == "query_loki_logs":
        query = arguments.get("query", "{}")
        limit = arguments.get("limit", 20)
        result = query_loki_logs(query=query, limit=limit)
        return result.model_dump()

    elif name == "get_pod_logs":
        return get_pod_logs(
            pod_name=arguments.get("pod_name", ""),
            namespace=arguments.get("namespace", "default"),
            tail_lines=arguments.get("tail_lines", 50),
            container=arguments.get("container", ""),
            previous=arguments.get("previous", False),
        )

    elif name == "diagnose_pod_health":
        pod_name = arguments.get("pod_name", "")
        namespace = arguments.get("namespace", "default")

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

        # Inspeccionar detalles de contenedor y exit codes
        pod_detail = get_pod_detail(pod_name=target_pod.name, namespace=namespace)
        for c in pod_detail.get("containers", []):
            last_st = c.get("last_state")
            if last_st and last_st.get("exit_code") is not None:
                issues.append(
                    f"Contenedor '{c['name']}' termino previamente con exit code {last_st['exit_code']} (razon: {last_st.get('reason', 'desconocida')})."
                )

        # Si hubo reinicios o fallo, agregar logs de la instancia previa
        if target_pod.restarts > 0 or target_pod.status in ["CrashLoopBackOff", "Failed", "OOMKilled"]:
            prev = get_pod_logs(pod_name=target_pod.name, namespace=namespace, tail_lines=5, previous=True)
            prev_content = prev.get("log", "")
            if prev_content and not prev_content.startswith("Error"):
                for line in prev_content.strip().split("\n")[-3:]:
                    if line.strip():
                        log_lines.append(f"[previous] {line.strip()}")

        if target_pod.status in ["CrashLoopBackOff", "Failed"]:
            issues.append(f"El pod esta en estado critico: {target_pod.status} con {target_pod.restarts} reinicios.")
            actions.append("Inspeccionar variables de entorno y conectividad a servicios dependientes.")
            actions.append("Revisar logs de la instancia anterior: get_pod_logs con previous=true.")
            score -= 60

        if target_pod.status == "OOMKilled" or any("OOMKilled" in ev for ev in related_events):
            issues.append("El pod fue terminado por superar el limite de memoria configurado (OOMKilled - Exit Code 137).")
            actions.append("Incrementar los limites de recursos en el Deployment (resources.limits.memory).")
            actions.append("Verificar tendencia de memoria: query_prometheus_range con container_memory_working_set_bytes.")
            score -= 50

        if target_pod.status == "Pending":
            issues.append("El pod esta en estado Pending: no se le ha asignado un nodo.")
            actions.append("Verificar estado de los nodos con get_cluster_nodes y eventos con get_cluster_events.")
            score -= 40

        if target_pod.status == "ImagePullBackOff" or any("ImagePullBackOff" in ev for ev in related_events):
            issues.append("No se puede descargar la imagen del contenedor (ImagePullBackOff).")
            actions.append("Verificar el tag de la imagen, el acceso al registry y los secrets de pull.")
            score -= 50

        if target_pod.status == "Running" and target_pod.restarts >= 5:
            issues.append(f"El pod esta corriendo pero acumula {target_pod.restarts} reinicios. Puede estar en un ciclo de crash/restart lento.")
            actions.append("Revisar logs de la instancia anterior con get_pod_logs(previous=true) para ver la causa del ultimo reinicio.")
            score -= 30

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
