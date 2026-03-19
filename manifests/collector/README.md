# Collector Manifests

This directory contains the OpenTelemetry Collector resources for the local PoC.

Highlights:

- A managed `OpenTelemetryCollector` named `demo-collector` in the `observability` namespace.
- OTLP receive endpoints on `4317` (gRPC) and `4318` (HTTP).
- A stable alias Service named `agent-observability-collector` so apps and generated `Instrumentation` resources can use a predictable endpoint.
- Trace export to `jaeger-collector.observability.svc.cluster.local:4317`.
- A `debug` exporter to make trace flow visible in Collector logs during local verification.

Install with:

```bash
./scripts/install-collector.sh
```
