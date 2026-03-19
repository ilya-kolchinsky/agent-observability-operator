# Collector Manifests

This directory contains a single demo-friendly `OpenTelemetryCollector` custom resource for the local PoC.

It is designed for the flow:

```text
app -> OTLP -> Collector -> Jaeger UI
```

Highlights:

- Runs as one managed `Deployment` in the `observability` namespace.
- Exposes OTLP over both gRPC (`4317`) and HTTP (`4318`).
- Exports traces to the local Jaeger all-in-one instance.
- Also uses the `debug` exporter so trace traffic is visible in Collector logs during local troubleshooting.

Install with:

```bash
./scripts/install-collector.sh
```
