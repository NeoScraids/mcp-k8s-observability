"""
Herramientas de inspeccion y diagnostico de Kubernetes para el servidor MCP.
"""

from typing import List
from datetime import datetime, timezone
from src.config import settings
from src.models import PodSummary, ClusterEvent


def get_pods(namespace: str = "default") -> List[PodSummary]:
    """
    Retorna la lista de pods y su estado en el namespace especificado.
    """
    if settings.is_mock:
        return [
            PodSummary(
                name="payments-service-7f89d5b4-kx9p2",
                namespace=namespace,
                status="Running",
                ready=True,
                restarts=0,
                age_seconds=86400,
                node_name="oke-pool1-node-01"
            ),
            PodSummary(
                name="auth-api-6b4c7d8e-mz3q1",
                namespace=namespace,
                status="Running",
                ready=True,
                restarts=2,
                age_seconds=172800,
                node_name="oke-pool1-node-02"
            ),
            PodSummary(
                name="notification-worker-5c9a1b2f-90rxt",
                namespace=namespace,
                status="CrashLoopBackOff",
                ready=False,
                restarts=14,
                age_seconds=3600,
                node_name="oke-pool1-node-03"
            ),
            PodSummary(
                name="analytics-exporter-4f11e9dc-pl45w",
                namespace=namespace,
                status="OOMKilled",
                ready=False,
                restarts=5,
                age_seconds=7200,
                node_name="oke-pool1-node-01"
            ),
        ]

    try:
        from kubernetes import client, config
        if settings.kubeconfig_path:
            config.load_kube_config(config_file=settings.kubeconfig_path)
        else:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()

        v1 = client.CoreV1Api()
        pod_list = v1.list_namespaced_pod(namespace=namespace)
        results = []
        now = datetime.now(timezone.utc)

        for pod in pod_list.items:
            restarts = 0
            is_ready = True
            if pod.status.container_statuses:
                for c in pod.status.container_statuses:
                    restarts += c.restart_count
                    if not c.ready:
                        is_ready = False

            age = 0
            if pod.metadata.creation_timestamp:
                age = int((now - pod.metadata.creation_timestamp).total_seconds())

            results.append(
                PodSummary(
                    name=pod.metadata.name,
                    namespace=namespace,
                    status=pod.status.phase or "Unknown",
                    ready=is_ready,
                    restarts=restarts,
                    age_seconds=age,
                    node_name=pod.spec.node_name
                )
            )
        return results
    except Exception as e:
        return [
            PodSummary(
                name="k8s-api-error",
                namespace=namespace,
                status=f"Error: {str(e)}",
                ready=False,
                restarts=0,
                age_seconds=0,
                node_name=None
            )
        ]


def get_events(namespace: str = "default") -> List[ClusterEvent]:
    """
    Retorna los eventos recientes de advertencia y error en el namespace.
    """
    if settings.is_mock:
        return [
            ClusterEvent(
                type="Warning",
                reason="BackOff",
                message="Back-off restarting failed container notification-worker in pod notification-worker-5c9a1b2f-90rxt",
                involved_object="Pod/notification-worker-5c9a1b2f-90rxt",
                count=14,
                last_timestamp="2026-09-10T20:30:00Z"
            ),
            ClusterEvent(
                type="Warning",
                reason="OOMKilled",
                message="Pod exceeded memory limit (512Mi). Container was terminated with exit code 137.",
                involved_object="Pod/analytics-exporter-4f11e9dc-pl45w",
                count=3,
                last_timestamp="2026-09-10T20:35:12Z"
            ),
            ClusterEvent(
                type="Normal",
                reason="Scheduled",
                message="Successfully assigned default/payments-service-7f89d5b4-kx9p2 to oke-pool1-node-01",
                involved_object="Pod/payments-service-7f89d5b4-kx9p2",
                count=1,
                last_timestamp="2026-09-10T19:00:00Z"
            )
        ]

    try:
        from kubernetes import client, config
        if settings.kubeconfig_path:
            config.load_kube_config(config_file=settings.kubeconfig_path)
        else:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()

        v1 = client.CoreV1Api()
        events_list = v1.list_namespaced_event(namespace=namespace)
        results = []

        for ev in events_list.items:
            results.append(
                ClusterEvent(
                    type=ev.type or "Normal",
                    reason=ev.reason or "Unknown",
                    message=ev.message or "",
                    involved_object=f"{ev.involved_object.kind}/{ev.involved_object.name}",
                    count=ev.count or 1,
                    last_timestamp=str(ev.last_timestamp or datetime.now(timezone.utc).isoformat())
                )
            )
        return results
    except Exception as e:
        return [
            ClusterEvent(
                type="Error",
                reason="APIError",
                message=f"No se pudieron obtener eventos de Kubernetes: {str(e)}",
                involved_object="Cluster",
                count=1,
                last_timestamp=datetime.now(timezone.utc).isoformat()
            )
        ]
