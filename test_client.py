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
        print(f"Herramienta: {tool['name']:<28} - {tool['description']}")

    print_section("3. EJECUTAR HERRAMIENTA: get_kubernetes_pods")
    pods_req = {
        "jsonrpc": "2.0",
        "id": 3,
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

    print_section("4. EJECUTAR HERRAMIENTA: query_prometheus_metrics (CPU)")
    prom_req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "query_prometheus_metrics",
            "arguments": {"query": "sum(rate(container_cpu_usage_seconds_total[5m])) by (pod)"}
        }
    }
    res = handle_json_rpc(prom_req)
    print(res["result"]["content"][0]["text"])

    print_section("5. EJECUTAR HERRAMIENTA: diagnose_pod_health (analytics-exporter)")
    diag_req = {
        "jsonrpc": "2.0",
        "id": 5,
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

    print_section("PRUEBAS MCP COMPLETADAS EXITOSAMENTE")


if __name__ == "__main__":
    run_tests()
