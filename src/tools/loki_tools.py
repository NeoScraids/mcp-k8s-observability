"""
Herramientas de consulta a Grafana Loki para el servidor MCP.
"""

from typing import Optional
import httpx
from src.config import settings
from src.models import LokiQueryResult


def query_loki_logs(query: str, limit: int = 20) -> LokiQueryResult:
    """
    Ejecuta una consulta LogQL contra Grafana Loki o retorna trazas de log sinteticas.
    """
    if settings.is_mock:
        entries = []
        if "error" in query.lower() or "fail" in query.lower():
            entries = [
                {"timestamp": "2026-09-10T20:34:10Z", "line": "level=error ts=2026-09-10T20:34:10Z caller=worker.go:112 msg='Failed to connect to Redis cache: connection refused'"},
                {"timestamp": "2026-09-10T20:34:25Z", "line": "level=error ts=2026-09-10T20:34:25Z caller=handler.go:89 msg='Max retries exceeded for queue notification.urgent' trace_id=8a7c2b3e4f1a2b3c"},
                {"timestamp": "2026-09-10T20:35:01Z", "line": "level=fatal ts=2026-09-10T20:35:01Z caller=main.go:45 msg='runtime memory exhausted: allocating 128MB chunk' exit_code=137"},
            ]
        else:
            entries = [
                {"timestamp": "2026-09-10T20:30:15Z", "line": "level=info ts=2026-09-10T20:30:15Z caller=http.go:50 method=POST path=/api/v1/payments status=200 duration_ms=45.2"},
                {"timestamp": "2026-09-10T20:30:18Z", "line": "level=info ts=2026-09-10T20:30:18Z caller=http.go:50 method=GET path=/health status=200 duration_ms=1.1"},
                {"timestamp": "2026-09-10T20:30:22Z", "line": "level=info ts=2026-09-10T20:30:22Z caller=auth.go:30 msg='Token verified successfully' user_id=usr_991823"},
            ]

        return LokiQueryResult(
            query=query,
            total_entries=len(entries),
            entries=entries[:limit]
        )

    try:
        url = f"{settings.loki_url}/loki/api/v1/query_range"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params={"query": query, "limit": limit})
            response.raise_for_status()
            data = response.json()

        entries = []
        result_items = data.get("data", {}).get("result", [])
        for stream in result_items:
            for value in stream.get("values", []):
                # Loki retorna timestamp en nanosegundos y linea de log
                entries.append({
                    "timestamp": str(value[0]),
                    "line": str(value[1])
                })

        return LokiQueryResult(
            query=query,
            total_entries=len(entries),
            entries=entries
        )
    except Exception as e:
        return LokiQueryResult(
            query=query,
            total_entries=1,
            entries=[{"timestamp": "0", "line": f"Error de consulta en Loki ({settings.loki_url}): {str(e)}"}]
        )
