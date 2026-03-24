FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install packages into /autoinstrumentation for OTel Operator compatibility
WORKDIR /autoinstrumentation

COPY custom-python-image/requirements.txt /tmp/custom-python-image-requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --target /autoinstrumentation -r /tmp/custom-python-image-requirements.txt \
    && rm -f /tmp/custom-python-image-requirements.txt

COPY runtime-coordinator /tmp/runtime-coordinator
RUN python -m pip install --target /autoinstrumentation /tmp/runtime-coordinator \
    && rm -rf /tmp/runtime-coordinator

# Replace OTel operator's sitecustomize.py with our enhanced version
COPY custom-python-image/src/sitecustomize.py /autoinstrumentation/opentelemetry/instrumentation/auto_instrumentation/sitecustomize.py

CMD ["python"]
