FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY demo-apps/requirements.txt /app/demo-apps/requirements.txt
RUN pip install --no-cache-dir -r /app/demo-apps/requirements.txt
COPY demo-apps/common /app/common
COPY demo-apps/agent-auto-httpx /app/agent-auto-httpx
EXPOSE 8000
CMD ["uvicorn", "main:app", "--app-dir", "/app/agent-auto-httpx", "--host", "0.0.0.0", "--port", "8000"]
