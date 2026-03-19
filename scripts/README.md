# Scripts

Helper scripts in this directory are aimed at a local Kubernetes demo environment, with kind as the preferred cluster option.

Dependency install flow:

1. `install-otel-operator.sh` installs cert-manager and the upstream OpenTelemetry Operator using raw manifests.
2. `install-jaeger.sh` applies the local Jaeger all-in-one manifest.
3. `install-collector.sh` applies the local Collector manifest.
4. `install-deps.sh` runs the three installers in that order.

The expected telemetry path for the PoC is:

```text
app -> OTLP -> Collector -> Jaeger UI
```
