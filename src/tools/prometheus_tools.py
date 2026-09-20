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
                    {"metric": {"job": "kubernetes-nodes", "instance": "k8s-node-01"}, "value": [1726000000, "1"]}
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


def query_prometheus_range(query: str, range_minutes: int = 15, step_seconds: int = 60) -> PromQueryResult:
    """Ejecuta una consulta PromQL sobre un rango de tiempo y retorna matrix de datapoints."""
    if settings.is_mock:
        import time as _time
        now = int(_time.time())
        steps = range_minutes * 60 // step_seconds
        # Simular tendencia ascendente de CPU para el pod problematico
        datapoints = []
        for i in range(steps):
            ts = now - (steps - i) * step_seconds
            val = round(0.3 + (i / steps) * 0.65, 3)  # sube de 0.3 a 0.95
            datapoints.append([ts, str(val)])

        return PromQueryResult(
            query=query,
            result_type="matrix",
            metrics_count=1,
            results=[
                {
                    "metric": {"pod": "analytics-exporter-4f11e9dc-pl45w", "namespace": "default"},
                    "values": datapoints
                }
            ]
        )

    try:
        import time as _time
        end = int(_time.time())
        start = end - (range_minutes * 60)
        url = f"{settings.prometheus_url}/api/v1/query_range"
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params={
                "query": query,
                "start": start,
                "end": end,
                "step": step_seconds,
            })
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "success":
            return PromQueryResult(query=query, result_type="error", metrics_count=0, results=[{"error": data.get("error")}])

        result_data = data.get("data", {})
        result_items = result_data.get("result", [])
        return PromQueryResult(
            query=query,
            result_type=result_data.get("resultType", "matrix"),
            metrics_count=len(result_items),
            results=result_items
        )
    except Exception as e:
        return PromQueryResult(
            query=query,
            result_type="error",
            metrics_count=0,
            results=[{"error": f"Fallo de conexion con Prometheus range query ({settings.prometheus_url}): {str(e)}"}]
        )

