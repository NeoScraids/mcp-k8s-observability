"""
Modelos de datos y esquemas Pydantic para el servidor MCP.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PodSummary(BaseModel):
    name: str = Field(description="Nombre del Pod")
    namespace: str = Field(description="Namespace de Kubernetes")
    status: str = Field(description="Fase del Pod (Running, Pending, Failed, etc.)")
    ready: bool = Field(description="Indica si todos los contenedores estan listos")
    restarts: int = Field(description="Cantidad total de reinicios de los contenedores")
    age_seconds: int = Field(description="Tiempo de vida en segundos")
    node_name: Optional[str] = Field(default=None, description="Nodo donde esta asignado")


class ClusterEvent(BaseModel):
    type: str = Field(description="Tipo de evento: Normal o Warning")
    reason: str = Field(description="Razon tecnica (e.g., BackOff, FailedScheduling, Unhealthy)")
    message: str = Field(description="Mensaje descriptivo del evento")
    involved_object: str = Field(description="Objeto de Kubernetes relacionado")
    count: int = Field(default=1, description="Numero de ocurrencias")
    last_timestamp: str = Field(description="Marca de tiempo del ultimo evento")


class PromQueryResult(BaseModel):
    query: str = Field(description="Consulta PromQL ejecutada")
    result_type: str = Field(description="Tipo de resultado (vector, matrix, scalar)")
    metrics_count: int = Field(description="Cantidad de series retornadas")
    results: List[Dict[str, Any]] = Field(description="Resultados estructurados con etiquetas y valores")


class LokiQueryResult(BaseModel):
    query: str = Field(description="Consulta LogQL ejecutada")
    total_entries: int = Field(description="Numero total de lineas de log retornadas")
    entries: List[Dict[str, str]] = Field(description="Lista de entradas con timestamp y mensaje")


class DiagnosticReport(BaseModel):
    pod_name: str
    namespace: str
    status: str
    health_score: int = Field(description="Puntuacion de salud de 0 a 100")
    detected_issues: List[str] = Field(description="Anomalias o problemas detectados")
    recommended_actions: List[str] = Field(description="Acciones recomendadas para SRE / DevOps")
    recent_logs: List[str] = Field(description="Ultimas lineas relevantes de log")
    recent_events: List[str] = Field(description="Eventos recientes asociados")
