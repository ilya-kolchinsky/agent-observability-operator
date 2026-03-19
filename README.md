# agent-observability-operator

This repository is a standalone end-to-end PoC for Python agent observability on Kubernetes. It includes:

- a custom `AgentObservabilityDemo` CRD and operator that prepare workloads for OpenTelemetry injection;
- a runtime coordinator embedded in a custom Python auto-instrumentation image;
- three demo FastAPI agent apps representing `no-existing`, `partial-existing`, and `full-existing` tracing ownership states;
- mock downstream MCP and HTTP services to generate realistic spans; and
- local manifests plus helper scripts that wire the full trace path from app -> Collector -> Jaeger.

## End-to-end telemetry path

```text
agent app
  -> OTLP HTTP (agent-observability-collector.observability.svc.cluster.local:4318)
  -> OpenTelemetry Collector
  -> Jaeger collector
  -> Jaeger UI (agent-observability-jaeger.observability.svc.cluster.local:16686)
```

## Stable service names

- Collector: `agent-observability-collector.observability.svc.cluster.local`
- Jaeger UI: `agent-observability-jaeger.observability.svc.cluster.local`
- Demo apps:
  - `agent-no-existing.demo-apps.svc.cluster.local`
  - `agent-partial-existing.demo-apps.svc.cluster.local`
  - `agent-full-existing.demo-apps.svc.cluster.local`
  - `mock-mcp-server.demo-apps.svc.cluster.local`
  - `mock-external-http-service.demo-apps.svc.cluster.local`

## Local kind workflow

Build and load images:

```bash
make build-images
make load-images-kind
```

Install the dependency layer:

```bash
make install-deps
```

Deploy the operator and demo apps, then apply the sample CRs:

```bash
make deploy-operator
make deploy-demo-apps
make apply-sample-crs
```

Send traffic and open Jaeger:

```bash
make send-demo-traffic
make port-forward-jaeger
```

Then browse to `http://127.0.0.1:16686`.

## Verifying the PoC

### 1. Verify the operator reconciled the CRs

```bash
kubectl get agentobservabilitydemos -n demo-apps
kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
```

Look for log entries such as:

- `reconciling AgentObservabilityDemo for end-to-end telemetry path`
- `created Instrumentation resource`
- `updated target Deployment for instrumentation injection`
- `updated AgentObservabilityDemo status after reconciliation`

### 2. Verify the OpenTelemetry Operator injected instrumentation

```bash
kubectl get pods -n demo-apps
kubectl describe pod -n demo-apps <agent-pod-name>
```

Check the Pod annotations and environment for:

- `instrumentation.opentelemetry.io/inject-python`
- `instrumentation.opentelemetry.io/container-names`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`

### 3. Verify the runtime coordinator chose a mode

```bash
kubectl logs -n demo-apps deployment/agent-no-existing --tail=100
kubectl logs -n demo-apps deployment/agent-partial-existing --tail=100
kubectl logs -n demo-apps deployment/agent-full-existing --tail=100
```

The runtime coordinator emits a JSON startup summary containing `selected_mode` and `selection_reason`. Expected modes for the PoC are:

- `agent-no-existing` -> `FULL`
- `agent-partial-existing` -> `AUGMENT`
- `agent-full-existing` -> `REUSE_EXISTING`

### 4. Verify traces reached Jaeger

```bash
kubectl logs -n observability deployment/demo-collector-collector --tail=200
kubectl port-forward -n observability svc/agent-observability-jaeger 16686:16686
```

The Collector uses both a `debug` exporter and an OTLP exporter to Jaeger, so the Collector logs should show trace export activity while the Jaeger UI should display spans for the demo agent services.

## Repository layout

- `operator/` - Custom operator source and unit tests.
- `runtime-coordinator/` - Python startup detection, mode selection, and activation logic.
- `custom-python-image/` - Custom Python auto-instrumentation image.
- `demo-apps/` - Demo agent and dependency services.
- `manifests/` - Kubernetes resources for CRD, operator, Collector, Jaeger, demo apps, and sample CRs.
- `scripts/` - Local workflow helpers for the end-to-end demo.
