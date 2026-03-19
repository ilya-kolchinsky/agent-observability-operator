# Jaeger Manifests

This directory contains a minimal Jaeger all-in-one deployment for a local demo cluster.

Included resources:

- `observability` namespace.
- `jaeger` deployment with OTLP enabled.
- `jaeger-query` service for the UI on port `16686`.
- `jaeger-collector` service exposing OTLP gRPC (`4317`) and HTTP (`4318`).

Install with:

```bash
./scripts/install-jaeger.sh
```

A convenient way to open the UI locally is:

```bash
kubectl port-forward -n observability svc/jaeger-query 16686:16686
```
