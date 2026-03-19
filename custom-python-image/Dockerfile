FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OTEL_SERVICE_NAME=python-agent

ARG INCLUDE_LANGCHAIN_INSTRUMENTATION=1

WORKDIR /opt/agent-observability

COPY custom-python-image/requirements.txt /tmp/custom-python-image-requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r /tmp/custom-python-image-requirements.txt \
    && if [ "$INCLUDE_LANGCHAIN_INSTRUMENTATION" = "1" ]; then \
        python -m pip install opentelemetry-instrumentation-langchain || true; \
       fi \
    && rm -f /tmp/custom-python-image-requirements.txt

COPY runtime-coordinator /tmp/runtime-coordinator
RUN python -m pip install /tmp/runtime-coordinator \
    && rm -rf /tmp/runtime-coordinator

COPY custom-python-image/src/sitecustomize.py /usr/local/lib/python3.11/site-packages/sitecustomize.py

CMD ["python"]
