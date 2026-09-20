from typing import Any, Dict, List
from datetime import datetime, timezone
from src.config import settings
from src.models import PodSummary, ClusterEvent


def _get_v1_client():
    from kubernetes import client, config
    if settings.kubeconfig_path:
        config.load_kube_config(config_file=settings.kubeconfig_path)
    else:
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()
    return client.CoreV1Api()


def get_pods(namespace: str = "default") -> List[PodSummary]:
    """Retorna la lista de pods y su estado en el namespace especificado."""
    if settings.is_mock:
        return [
            PodSummary(
                name="payments-service-7f89d5b4-kx9p2",
                namespace=namespace,
                status="Running",
                ready=True,
                restarts=0,
                age_seconds=86400,
                node_name="k8s-node-01"
            ),
            PodSummary(
                name="auth-api-6b4c7d8e-mz3q1",
                namespace=namespace,
                status="Running",
                ready=True,
                restarts=2,
                age_seconds=172800,
                node_name="k8s-node-02"
            ),
            PodSummary(
                name="notification-worker-5c9a1b2f-90rxt",
                namespace=namespace,
                status="CrashLoopBackOff",
                ready=False,
                restarts=14,
                age_seconds=3600,
                node_name="k8s-node-03"
            ),
            PodSummary(
                name="analytics-exporter-4f11e9dc-pl45w",
                namespace=namespace,
                status="OOMKilled",
                ready=False,
                restarts=5,
                age_seconds=7200,
                node_name="k8s-node-01"
            ),
        ]

    try:
        v1 = _get_v1_client()
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
    """Retorna los eventos recientes de advertencia y error en el namespace."""
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
                message="Successfully assigned default/payments-service-7f89d5b4-kx9p2 to k8s-node-01",
                involved_object="Pod/payments-service-7f89d5b4-kx9p2",
                count=1,
                last_timestamp="2026-09-10T19:00:00Z"
            )
        ]

    try:
        v1 = _get_v1_client()
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


def list_namespaces() -> List[Dict[str, str]]:
    """Retorna los namespaces disponibles en el cluster."""
    if settings.is_mock:
        return [
            {"name": "default", "status": "Active", "created": "2025-04-01T00:00:00Z"},
            {"name": "payments", "status": "Active", "created": "2025-04-15T10:30:00Z"},
            {"name": "monitoring", "status": "Active", "created": "2025-04-15T10:35:00Z"},
            {"name": "kube-system", "status": "Active", "created": "2025-04-01T00:00:00Z"},
        ]

    try:
        v1 = _get_v1_client()
        ns_list = v1.list_namespace()
        return [
            {
                "name": ns.metadata.name,
                "status": ns.status.phase or "Unknown",
                "created": str(ns.metadata.creation_timestamp or ""),
            }
            for ns in ns_list.items
        ]
    except Exception as e:
        return [{"name": "error", "status": f"APIError: {str(e)}", "created": ""}]


def get_pod_logs(
    pod_name: str,
    namespace: str = "default",
    tail_lines: int = 50,
    container: str = "",
    previous: bool = False,
) -> Dict[str, Any]:
    """Obtiene las ultimas N lineas de log de un pod via API de Kubernetes."""
    if settings.is_mock:
        if previous:
            lines = [
                "2026-09-19T09:14:02Z [main] Starting payments-processor v2.13.8",
                "2026-09-19T09:14:03Z [main] Connecting to PostgreSQL at pgbouncer.database.svc:5432",
                "2026-09-19T09:14:03Z [hikari] Pool initialized: max=20, min=5, idle_timeout=300s",
                "2026-09-19T09:15:41Z [worker] Processing batch: 1,847 pending transactions",
                "2026-09-19T09:15:42Z [worker] java.lang.OutOfMemoryError: Java heap space",
                "2026-09-19T09:15:42Z [worker]   at com.payments.batch.TransactionAggregator.loadChunk(TransactionAggregator.java:89)",
                "2026-09-19T09:15:42Z [main] Shutting down: OOM (exit code 137)",
            ]
        else:
            lines = [
                "2026-09-19T10:58:01Z [main] Starting payments-processor v2.13.8",
                "2026-09-19T10:58:02Z [main] Connecting to PostgreSQL at pgbouncer.database.svc:5432",
                "2026-09-19T10:58:02Z [hikari] Pool initialized: max=20, min=5, idle_timeout=300s",
                "2026-09-19T10:58:05Z [health] Readiness probe: OK",
                "2026-09-19T10:58:30Z [worker] Processed 312 transactions in 25.1s (avg 80.4ms/tx)",
                "2026-09-19T11:00:01Z [health] Liveness probe: OK",
                "2026-09-19T11:03:15Z [worker] Processed 287 transactions in 22.8s (avg 79.4ms/tx)",
            ]

        return {
            "pod": pod_name,
            "namespace": namespace,
            "container": container or "(default)",
            "previous": previous,
            "tail_lines": tail_lines,
            "log": "\n".join(lines[-tail_lines:]),
        }

    try:
        v1 = _get_v1_client()
        kwargs = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines,
            "previous": previous,
        }
        if container:
            kwargs["container"] = container

        log_output = v1.read_namespaced_pod_log(**kwargs)

        return {
            "pod": pod_name,
            "namespace": namespace,
            "container": container or "(default)",
            "previous": previous,
            "tail_lines": tail_lines,
            "log": log_output,
        }
    except Exception as e:
        return {
            "pod": pod_name,
            "namespace": namespace,
            "container": container or "(default)",
            "previous": previous,
            "tail_lines": tail_lines,
            "log": f"Error leyendo logs: {str(e)}",
        }


def get_pod_detail(pod_name: str, namespace: str = "default") -> Dict[str, Any]:
    """Obtiene informacion detallada de un pod (contenedores, exit codes, limits, condiciones)."""
    if settings.is_mock:
        if "notification-worker" in pod_name:
            return {
                "name": pod_name,
                "namespace": namespace,
                "phase": "Running",
                "node_name": "k8s-node-03",
                "pod_ip": "10.244.3.42",
                "start_time": "2026-09-19T08:15:00Z",
                "containers": [
                    {
                        "name": "notification-worker",
                        "image": "registry.internal/notification-worker:v1.4.2",
                        "ready": False,
                        "restarts": 14,
                        "state": "waiting",
                        "waiting_reason": "CrashLoopBackOff",
                        "last_state": {
                            "exit_code": 1,
                            "reason": "Error",
                            "finished_at": "2026-09-19T11:02:10Z",
                        },
                        "requests": {"cpu": "50m", "memory": "128Mi"},
                        "limits": {"cpu": "200m", "memory": "256Mi"},
                    }
                ],
                "conditions": [
                    {"type": "PodScheduled", "status": "True"},
                    {"type": "Initialized", "status": "True"},
                    {"type": "ContainersReady", "status": "False"},
                    {"type": "Ready", "status": "False"},
                ],
            }
        elif "analytics-exporter" in pod_name:
            return {
                "name": pod_name,
                "namespace": namespace,
                "phase": "Running",
                "node_name": "k8s-node-01",
                "pod_ip": "10.244.1.29",
                "start_time": "2026-09-19T09:00:00Z",
                "containers": [
                    {
                        "name": "analytics-exporter",
                        "image": "registry.internal/analytics-exporter:v0.9.1",
                        "ready": False,
                        "restarts": 5,
                        "state": "waiting",
                        "waiting_reason": "CrashLoopBackOff",
                        "last_state": {
                            "exit_code": 137,
                            "reason": "OOMKilled",
                            "finished_at": "2026-09-19T10:45:00Z",
                        },
                        "requests": {"cpu": "100m", "memory": "256Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    }
                ],
                "conditions": [
                    {"type": "PodScheduled", "status": "True"},
                    {"type": "Initialized", "status": "True"},
                    {"type": "ContainersReady", "status": "False"},
                    {"type": "Ready", "status": "False"},
                ],
            }
        else:
            return {
                "name": pod_name,
                "namespace": namespace,
                "phase": "Running",
                "node_name": "k8s-node-01",
                "pod_ip": "10.244.1.18",
                "start_time": "2026-09-18T10:00:00Z",
                "containers": [
                    {
                        "name": "payments-service",
                        "image": "registry.internal/payments:v2.13.8",
                        "ready": True,
                        "restarts": 0,
                        "state": "running",
                        "last_state": None,
                        "requests": {"cpu": "100m", "memory": "256Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    }
                ],
                "conditions": [
                    {"type": "PodScheduled", "status": "True"},
                    {"type": "Initialized", "status": "True"},
                    {"type": "ContainersReady", "status": "True"},
                    {"type": "Ready", "status": "True"},
                ],
            }

    try:
        v1 = _get_v1_client()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        containers = []
        statuses = {s.name: s for s in (pod.status.container_statuses or [])}
        for c in pod.spec.containers:
            st = statuses.get(c.name)
            ready = st.ready if st else False
            restarts = st.restart_count if st else 0
            state = "unknown"
            waiting_reason = None
            last_state = None

            if st and st.state:
                if st.state.running:
                    state = "running"
                elif st.state.waiting:
                    state = "waiting"
                    waiting_reason = st.state.waiting.reason
                elif st.state.terminated:
                    state = "terminated"

            if st and st.last_state and st.last_state.terminated:
                term = st.last_state.terminated
                last_state = {
                    "exit_code": term.exit_code,
                    "reason": term.reason,
                    "finished_at": str(term.finished_at or ""),
                }

            reqs = c.resources.requests if c.resources else {}
            limits = c.resources.limits if c.resources else {}

            containers.append({
                "name": c.name,
                "image": c.image,
                "ready": ready,
                "restarts": restarts,
                "state": state,
                "waiting_reason": waiting_reason,
                "last_state": last_state,
                "requests": dict(reqs) if reqs else {},
                "limits": dict(limits) if limits else {},
            })

        conditions = []
        for cond in (pod.status.conditions or []):
            conditions.append({
                "type": cond.type,
                "status": cond.status,
                "reason": cond.reason or "",
                "message": cond.message or "",
            })

        return {
            "name": pod.metadata.name,
            "namespace": namespace,
            "phase": pod.status.phase or "Unknown",
            "node_name": pod.spec.node_name,
            "pod_ip": pod.status.pod_ip,
            "start_time": str(pod.status.start_time or ""),
            "containers": containers,
            "conditions": conditions,
        }
    except Exception as e:
        return {
            "name": pod_name,
            "namespace": namespace,
            "phase": "Error",
            "error": str(e),
            "containers": [],
            "conditions": [],
        }


def get_cluster_nodes() -> List[Dict[str, Any]]:
    """Retorna la lista de nodos del cluster con estado, capacidad y condiciones."""
    if settings.is_mock:
        return [
            {
                "name": "k8s-node-01",
                "status": "Ready",
                "roles": ["worker"],
                "version": "v1.29.4",
                "internal_ip": "10.0.1.10",
                "capacity": {"cpu": "8", "memory": "32Gi", "pods": "110"},
                "allocatable": {"cpu": "7800m", "memory": "30Gi", "pods": "110"},
                "conditions": {"Ready": "True", "MemoryPressure": "False", "DiskPressure": "False", "PIDPressure": "False"},
            },
            {
                "name": "k8s-node-02",
                "status": "Ready",
                "roles": ["worker"],
                "version": "v1.29.4",
                "internal_ip": "10.0.1.11",
                "capacity": {"cpu": "8", "memory": "32Gi", "pods": "110"},
                "allocatable": {"cpu": "7800m", "memory": "30Gi", "pods": "110"},
                "conditions": {"Ready": "True", "MemoryPressure": "False", "DiskPressure": "False", "PIDPressure": "False"},
            },
            {
                "name": "k8s-node-03",
                "status": "Ready",
                "roles": ["worker"],
                "version": "v1.29.4",
                "internal_ip": "10.0.1.12",
                "capacity": {"cpu": "8", "memory": "32Gi", "pods": "110"},
                "allocatable": {"cpu": "7800m", "memory": "30Gi", "pods": "110"},
                "conditions": {"Ready": "True", "MemoryPressure": "False", "DiskPressure": "False", "PIDPressure": "False"},
            },
        ]

    try:
        v1 = _get_v1_client()
        nodes = v1.list_node()
        results = []
        for node in nodes.items:
            conditions = {}
            status = "Unknown"
            for cond in (node.status.conditions or []):
                conditions[cond.type] = cond.status
                if cond.type == "Ready" and cond.status == "True":
                    status = "Ready"
                elif cond.type == "Ready" and cond.status != "True":
                    status = "NotReady"

            roles = []
            for label in (node.metadata.labels or {}):
                if label.startswith("node-role.kubernetes.io/"):
                    roles.append(label.split("/")[1])
            if not roles:
                roles = ["worker"]

            ip = ""
            for addr in (node.status.addresses or []):
                if addr.type == "InternalIP":
                    ip = addr.address

            results.append({
                "name": node.metadata.name,
                "status": status,
                "roles": roles,
                "version": node.status.node_info.kubelet_version if node.status.node_info else "",
                "internal_ip": ip,
                "capacity": dict(node.status.capacity) if node.status.capacity else {},
                "allocatable": dict(node.status.allocatable) if node.status.allocatable else {},
                "conditions": conditions,
            })
        return results
    except Exception as e:
        return [{"name": "error", "status": f"APIError: {str(e)}", "conditions": {}}]
