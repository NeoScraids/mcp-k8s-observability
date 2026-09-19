.PHONY: setup test mock run-stdio docker-build docker-run lint clean

# Levantar entorno local
setup:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp -n .env.example .env 2>/dev/null || true

# Correr pruebas del cliente MCP en modo mock
test:
	MCP_MODE=mock python test_client.py

# Alias de test
mock: test

# Iniciar servidor en modo stdio (para Claude Desktop)
run-stdio:
	python -m src.server

# Docker
docker-build:
	docker build -t mcp-k8s-observability:latest .

docker-run:
	docker run --rm -i --env-file .env mcp-k8s-observability:latest

# Lint basico con ruff (si esta instalado)
lint:
	python -m ruff check src/ test_client.py --select E,F,W

# Limpiar artefactos
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf venv/ .ruff_cache/
