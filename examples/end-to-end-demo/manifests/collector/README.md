# Collector Manifests

This directory contains the OpenTelemetry Collector resources for the demo.

## What's Included

- A managed `OpenTelemetryCollector` named `demo-collector` in the `observability` namespace
- OTLP receive endpoints on `4317` (gRPC) and `4318` (HTTP)
- A stable alias Service named `agent-observability-collector` so apps and generated `Instrumentation` resources can use a predictable endpoint
- Trace export to `jaeger-collector.observability.svc.cluster.local:4317`
- A `debug` exporter to make trace flow visible in Collector logs during local verification

## Install

```bash
examples/end-to-end-demo/scripts/install-collector.sh
```

Or via Makefile:

```bash
make install-collector
```

## Verify

Check that the Collector is running:

```bash
kubectl get pods -n observability
kubectl logs -n observability deployment/demo-collector-collector --tail=100
```

## Configuration

The Collector is configured to:
- Receive traces via OTLP (gRPC and HTTP)
- Export traces to Jaeger
- Log traces to stdout for debugging

Service endpoints:
- `demo-collector-collector.observability.svc.cluster.local:4317` (gRPC)
- `demo-collector-collector.observability.svc.cluster.local:4318` (HTTP)
- `agent-observability-collector.observability.svc.cluster.local:4318` (stable alias)
