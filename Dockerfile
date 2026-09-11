FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY src/ ./src/
COPY test_client.py .

ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=mock

ENTRYPOINT ["python", "-m", "src.server"]
