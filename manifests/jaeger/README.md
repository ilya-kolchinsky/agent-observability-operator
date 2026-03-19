# Jaeger Manifests

This directory contains the Jaeger all-in-one deployment for the local PoC.

Included resources:

- `observability` namespace
- `jaeger` deployment with OTLP ingest enabled
- `agent-observability-jaeger` UI service on port `16686`
- `jaeger-collector` OTLP service on ports `4317` and `4318`

Install with:

```bash
./scripts/install-jaeger.sh
```

Port-forward the UI locally with:

```bash
./scripts/port-forward-jaeger.sh
```
