"""
Cliente de prueba CLI para verificar el servidor MCP localmente sin necesidad de clientes externos.
"""

import json
from src.server import handle_json_rpc


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_tests():
    print_section("1. INICIALIZACION MCP (initialize)")
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    res = handle_json_rpc(init_req)
    print(json.dumps(res, indent=2, ensure_ascii=False))

    print_section("2. LISTADO DE HERRAMIENTAS DISPONIBLES (tools/list)")
    tools_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    res = handle_json_rpc(tools_req)
    for tool in res["result"]["tools"]:
        print(f"Herramienta: {tool['name']:<28} - {tool['description'][:80]}")

    print_section("3. LIST NAMESPACES")
    ns_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "list_namespaces", "arguments": {}}
    }
    res = handle_json_rpc(ns_req)
    namespaces = json.loads(res["result"]["content"][0]["text"])
    for ns in namespaces:
        print(f"  {ns['name']:<20} {ns['status']:<12} created: {ns['created']}")

    print_section("4. GET KUBERNETES PODS")
    pods_req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_kubernetes_pods",
            "arguments": {"namespace": "default"}
        }
    }
    res = handle_json_rpc(pods_req)
    content = json.loads(res["result"]["content"][0]["text"])
    for p in content:
        status_flag = "[OK]" if p["ready"] else "[FAIL]"
        print(f"{status_flag:<7} Pod: {p['name']:<42} Estado: {p['status']:<18} Reinicios: {p['restarts']}")

    print_section("5. PROMETHEUS INSTANT QUERY (CPU)")
    prom_req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "query_prometheus_metrics",
            "arguments": {"query": "sum(rate(container_cpu_usage_seconds_total[5m])) by (pod)"}
        }
    }
    res = handle_json_rpc(prom_req)
    print(res["result"]["content"][0]["text"])

    print_section("6. PROMETHEUS RANGE QUERY (CPU tendencia 15min)")
    range_req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "query_prometheus_range",
            "arguments": {
                "query": "rate(container_cpu_usage_seconds_total[5m])",
                "range_minutes": 15,
                "step_seconds": 60
            }
        }
    }
    res = handle_json_rpc(range_req)
    range_data = json.loads(res["result"]["content"][0]["text"])
    print(f"  Tipo: {range_data['result_type']}, Series: {range_data['metrics_count']}")
    if range_data["results"]:
        values = range_data["results"][0].get("values", [])
        print(f"  Datapoints: {len(values)} (primero: {values[0][1] if values else '-'}, ultimo: {values[-1][1] if values else '-'})")

    print_section("7. GET POD LOGS (instancia actual)")
    logs_req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "get_pod_logs",
            "arguments": {"pod_name": "payments-service-7f89d5b4-kx9p2", "tail_lines": 5}
        }
    }
    res = handle_json_rpc(logs_req)
    log_data = json.loads(res["result"]["content"][0]["text"])
    print(f"  Pod: {log_data['pod']} | Previous: {log_data['previous']}")
    for line in log_data["log"].split("\n"):
        print(f"    {line}")

    print_section("8. GET POD LOGS (instancia ANTERIOR - --previous)")
    prev_req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "get_pod_logs",
            "arguments": {"pod_name": "payments-service-7f89d5b4-kx9p2", "previous": True, "tail_lines": 10}
        }
    }
    res = handle_json_rpc(prev_req)
    log_data = json.loads(res["result"]["content"][0]["text"])
    print(f"  Pod: {log_data['pod']} | Previous: {log_data['previous']}")
    for line in log_data["log"].split("\n"):
        print(f"    {line}")

    print_section("9. DIAGNOSTICO: analytics-exporter (OOMKilled)")
    diag_req = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "diagnose_pod_health",
            "arguments": {"pod_name": "analytics-exporter", "namespace": "default"}
        }
    }
    res = handle_json_rpc(diag_req)
    diag_data = json.loads(res["result"]["content"][0]["text"])
    print(f"Pod Objetivo:       {diag_data['pod_name']}")
    print(f"Puntuacion Salud:   {diag_data['health_score']}/100")
    print(f"Problemas Hallados: {', '.join(diag_data['detected_issues'])}")
    print(f"Acciones SRE:       {', '.join(diag_data['recommended_actions'])}")
    print("\nLogs Recientes:")
    for log in diag_data['recent_logs']:
        print(f"  {log}")

    print_section("10. GET POD DETAIL (analisis profundo de contenedor y limits)")
    detail_req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "get_pod_detail",
            "arguments": {"pod_name": "analytics-exporter-4f11e9dc-pl45w", "namespace": "default"}
        }
    }
    res = handle_json_rpc(detail_req)
    detail_data = json.loads(res["result"]["content"][0]["text"])
    print(f"  Pod: {detail_data['name']} | IP: {detail_data['pod_ip']} | Nodo: {detail_data['node_name']}")
    for c in detail_data.get("containers", []):
        print(f"    Contenedor: {c['name']} (ready={c['ready']}, restarts={c['restarts']})")
        if c.get("last_state"):
            print(f"      Last State: exit_code={c['last_state'].get('exit_code')} reason={c['last_state'].get('reason')}")
        print(f"      Requests: {c.get('requests')} | Limits: {c.get('limits')}")

    print_section("11. GET CLUSTER NODES (capacidad y condiciones)")
    nodes_req = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "get_cluster_nodes", "arguments": {}}
    }
    res = handle_json_rpc(nodes_req)
    nodes_data = json.loads(res["result"]["content"][0]["text"])
    for n in nodes_data:
        cond_str = ", ".join([f"{k}={v}" for k, v in n["conditions"].items() if k == "Ready" or v == "True"])
        print(f"  Nodo: {n['name']:<16} Estado: {n['status']:<10} IP: {n['internal_ip']:<14} Cond: {cond_str}")

    print_section("PRUEBAS MCP COMPLETADAS EXITOSAMENTE")
    tools_count = len(handle_json_rpc(tools_req)["result"]["tools"])
    print(f"  Herramientas verificadas: {tools_count}")
    print(f"  Modo: mock\n")


if __name__ == "__main__":
    run_tests()
