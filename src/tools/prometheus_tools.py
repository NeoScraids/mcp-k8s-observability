"""
Herramientas de consulta a Prometheus para el servidor MCP.
"""

import httpx
from src.config import settings
from src.models import PromQueryResult


def query_prometheus(query: str) -> PromQueryResult:
    """
    Ejecuta una consulta PromQL contra Prometheus o retorna simulacion realista.
    """
    if settings.is_mock:
        if "cpu" in query.lower():
            return PromQueryResult(
                query=query,
                result_type="vector",
                metrics_count=3,
                results=[
                    {"metric": {"pod": "payments-service-7f89d5b4-kx9p2", "namespace": "default"}, "value": [1726000000, "0.145"]},
                    {"metric": {"pod": "auth-api-6b4c7d8e-mz3q1", "namespace": "default"}, "value": [1726000000, "0.420"]},
                    {"metric": {"pod": "analytics-exporter-4f11e9dc-pl45w", "namespace": "default"}, "value": [1726000000, "0.985"]},
                ]
            )
        elif "memory" in query.lower():
            return PromQueryResult(
                query=query,
                result_type="vector",
                metrics_count=2,
                results=[
                    {"metric": {"pod": "payments-service-7f89d5b4-kx9p2", "namespace": "default"}, "value": [1726000000, "268435456"]}, # 256 MiB
                    {"metric": {"pod": "analytics-exporter-4f11e9dc-pl45w", "namespace": "default"}, "value": [1726000000, "536870912"]}, # 512 MiB (al limite)
                ]
            )
        else:
            return PromQueryResult(
                query=query,
                result_type="vector",
                metrics_count=1,
                results=[
                    {"metric": {"job": "kubernetes-nodes", "instance": "oke-pool1-node-01"}, "value": [1726000000, "1"]}
                ]
            )

    try:
        url = f"{settings.prometheus_url}/api/v1/query"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params={"query": query})
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "success":
            return PromQueryResult(query=query, result_type="error", metrics_count=0, results=[{"error": data.get("error")}])

        result_data = data.get("data", {})
        result_items = result_data.get("result", [])
        return PromQueryResult(
            query=query,
            result_type=result_data.get("resultType", "unknown"),
            metrics_count=len(result_items),
            results=result_items
        )
    except Exception as e:
        return PromQueryResult(
            query=query,
            result_type="error",
            metrics_count=0,
            results=[{"error": f"Fallo de conexion con Prometheus ({settings.prometheus_url}): {str(e)}"}]
        )
