# Jaeger Manifests

This directory contains the Jaeger all-in-one deployment for the demo.

## What's Included

- `observability` namespace
- `jaeger` deployment with OTLP ingest enabled
- `agent-observability-jaeger` UI service on port `16686`
- `jaeger-collector` OTLP service on ports `4317` (gRPC) and `4318` (HTTP)

## Install

```bash
examples/end-to-end-demo/scripts/install-jaeger.sh
```

Or via Makefile:

```bash
make install-jaeger
```

## Access Jaeger UI

Port-forward the UI to your local machine:

```bash
examples/end-to-end-demo/scripts/port-forward-jaeger.sh
```

Or via Makefile:

```bash
make port-forward-jaeger
```

Then open http://127.0.0.1:16686 in your browser.

## Verify

Check that Jaeger is running:

```bash
kubectl get pods -n observability
kubectl logs -n observability deployment/jaeger --tail=100
```

## Service Endpoints

Inside the cluster:
- UI: `agent-observability-jaeger.observability.svc.cluster.local:16686`
- OTLP gRPC: `jaeger-collector.observability.svc.cluster.local:4317`
- OTLP HTTP: `jaeger-collector.observability.svc.cluster.local:4318`

## Storage

**Note:** This Jaeger deployment uses in-memory storage for simplicity. Traces are lost when the pod restarts. For persistent storage, you would need to configure a backend like Elasticsearch or Cassandra.
