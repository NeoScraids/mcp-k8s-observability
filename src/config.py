"""
Modulo de configuracion del servidor MCP de observabilidad y Kubernetes.
Soporta modo 'live' para integraciones reales y modo 'mock' para pruebas desatendidas.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("MCP_MODE", "mock").lower()
    prometheus_url: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
    loki_url: str = os.getenv("LOKI_URL", "http://localhost:3100").rstrip("/")
    kubeconfig_path: str = os.getenv("KUBECONFIG", "")
    host: str = os.getenv("MCP_HOST", "0.0.0.0")
    port: int = int(os.getenv("MCP_PORT", "8000"))

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"


settings = Settings()
