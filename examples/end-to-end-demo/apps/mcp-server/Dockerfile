FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY examples/end-to-end-demo/apps/requirements.txt /app/examples/end-to-end-demo/apps/requirements.txt
RUN pip install --no-cache-dir -r /app/examples/end-to-end-demo/apps/requirements.txt
COPY examples/end-to-end-demo/apps/common /app/common
COPY examples/end-to-end-demo/apps/mcp-server /app/mcp-server
EXPOSE 8000
CMD ["uvicorn", "main:app", "--app-dir", "/app/mcp-server", "--host", "0.0.0.0", "--port", "8000"]
