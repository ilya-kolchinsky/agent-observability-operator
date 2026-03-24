# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Kubernetes operator that demonstrates Python agent observability with runtime-controlled auto-instrumentation. The system has two main layers:

1. **Control plane** (Go operator): Reconciles `AgentObservabilityDemo` CRs into OpenTelemetry `Instrumentation` resources and patches target workloads
2. **Runtime** (Python coordinator): Makes startup-time instrumentation decisions based on detected ownership signals, using fine-grained per-framework decision functions

## Build Commands

### Build operator
```bash
cd operator
go build -o bin/manager main.go
```

### Build all Docker images
```bash
make build-images
```

This builds:
- Operator image (`agent-observability/operator`)
- Custom Python auto-instrumentation image (`agent-observability/custom-python-autoinstrumentation`)
- Three demo agent images (`agent-observability/agent-{no,partial,full}-existing`)
- Mock MCP server and HTTP service images

### Load images into kind
```bash
make load-images-kind
```

## Testing

### Run operator tests
```bash
cd operator
go test ./internal/controller/...
```

### Run runtime coordinator tests
```bash
cd runtime-coordinator
python -m pytest tests/
```

## Development Workflow

### Full demo cycle
```bash
make demo-walkthrough
```

### Step-by-step development
```bash
make create-kind-cluster
make install-deps
make build-images
make load-images-kind
make deploy-operator
make deploy-demo-apps
make apply-sample-crs
make verify-demo
make send-demo-traffic
```

### Verify operator reconciliation
```bash
kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
kubectl get agentobservabilitydemos -n demo-apps
kubectl get instrumentation -n demo-apps
```

### Verify runtime coordinator decisions
```bash
kubectl logs -n demo-apps deployment/agent-no-existing --tail=200
kubectl logs -n demo-apps deployment/agent-partial-existing --tail=200
kubectl logs -n demo-apps deployment/agent-full-existing --tail=200
```

Look for the `detection_complete` event with `decisions` object in the startup diagnostics JSON.

### Port-forward Jaeger UI
```bash
make port-forward-jaeger
# Open http://127.0.0.1:16686
```

## Architecture

### Reconciliation flow

When an `AgentObservabilityDemo` CR is applied:

1. **Operator creates OTel `Instrumentation` resource** in target namespace
2. **Operator creates runtime coordinator `ConfigMap`** with heuristics/patchers settings
3. **Operator patches target Deployment**:
   - Adds `instrumentation.opentelemetry.io/inject-python` annotation
   - Adds `instrumentation.opentelemetry.io/container-names` annotation
   - Injects OTLP environment variables into selected container
   - Mounts runtime coordinator config file
4. **OTel Operator injects auto-instrumentation** into workload pods
5. **Custom Python image starts with `sitecustomize.py`** invoking runtime coordinator
6. **Runtime coordinator detects ownership signals** and selects mode
7. **Runtime coordinator applies fine-grained instrumentation decisions** based on detection results

### Runtime coordinator decision logic

The coordinator makes independent decisions for each instrumentation target:

- **initialize_provider**: Initialize TracerProvider if only ProxyTracerProvider detected
- **instrument_fastapi**: Instrument FastAPI if available and not already instrumented
- **instrument_httpx**: Instrument httpx if available and not already instrumented
- **instrument_requests**: Instrument requests if available and not already instrumented
- **instrument_langchain**: Instrument LangChain if available and not already instrumented
- **instrument_langgraph**: Instrument LangGraph if available and not already instrumented
- **instrument_mcp**: Instrument MCP boundaries if available and not already instrumented

### Operator code structure

- `operator/main.go` - operator entrypoint, manager setup
- `operator/api/v1alpha1/agentobservability_types.go` - CRD API types (AgentObservabilityDemo spec/status)
- `operator/internal/controller/agentobservability_controller.go` - reconciliation logic
- `operator/stubs/` - type stubs for k8s and OTel Operator APIs (used instead of full dependencies)

### Runtime coordinator structure

- `runtime-coordinator/agent_obs_runtime/bootstrap.py` - startup orchestration and diagnostics emission
- `runtime-coordinator/agent_obs_runtime/detection.py` - ownership signal detection and decision functions
- `runtime-coordinator/agent_obs_runtime/instrumentation.py` - instrumentation actuation for all frameworks
- `custom-python-image/src/sitecustomize.py` - invokes coordinator at Python startup (replaces OTel operator's sitecustomize.py)

### Demo app structure

All three demo agents share the same workload (FastAPI + LangGraph + MCP + httpx):

- `demo-apps/agent-no-existing/` - no tracing setup in main.py
- `demo-apps/agent-partial-existing/` - partial tracing setup (provider + basic HTTP) in main.py
- `demo-apps/agent-full-existing/` - full tracing setup (provider + all instrumentations) in main.py
- `demo-apps/common/` - shared LangGraph workflow, MCP client, logging, tracing helpers

**Note**: Due to the sitecustomize timing issue, all three apps currently show identical coordinator decisions since sitecustomize runs before main.py.

## Key Configuration

### Custom resource spec fields

- `spec.target.{namespace,workloadName,workloadKind,containerName}` - target for instrumentation
- `spec.instrumentation.customPythonImage` - custom auto-instrumentation image reference
- `spec.instrumentation.otelCollectorEndpoint` - OTLP endpoint for traces
- `spec.runtimeCoordinator.enabled` - enable/disable runtime coordinator
- `spec.runtimeCoordinator.diagnosticsLevel` - verbosity of startup diagnostics
- `spec.runtimeCoordinator.heuristics.*` - detection heuristic toggles
- `spec.runtimeCoordinator.patchers.*` - instrumentation target toggles

### Environment variables used by runtime coordinator

- `AGENT_OBS_MODE` - explicit mode override
- `AGENT_OBS_CONFIG_FILE` - path to mounted coordinator config
- `AGENT_OBS_DIAGNOSTICS_LEVEL` - diagnostics verbosity
- `AGENT_OBS_ENABLED_HEURISTICS` - comma-separated list of enabled heuristics
- `AGENT_OBS_ENABLED_PATCHERS` - comma-separated list of enabled patchers

## Important Constraints

- **Operator only patches Deployment workloads** in this PoC (not StatefulSets/DaemonSets)
- **Operator uses ConfigMap-based coordinator config** rather than encoding everything in env vars
- **Runtime coordinator is PoC-focused** with simplified heuristics, not production-grade semantic analysis
- **Supported Python frameworks**: FastAPI, ASGI, httpx, requests, MCP boundaries, LangChain, LangGraph
- **Local kind cluster only** - images are built locally and loaded into kind, not pushed to a registry

## Telemetry Path

```
Demo agent
  → OTLP HTTP (agent-observability-collector.observability.svc.cluster.local:4318)
  → OpenTelemetry Collector
  → Jaeger collector
  → Jaeger UI (port-forward to localhost:16686)
```

## Making Changes

### Modifying operator reconciliation logic

Edit `operator/internal/controller/agentobservability_controller.go`, rebuild operator image, reload into kind, redeploy operator.

### Modifying runtime coordinator behavior

Edit files in `runtime-coordinator/agent_obs_runtime/`, rebuild custom Python image, reload into kind. Existing pods need to be deleted to pick up new image.

### Modifying CRD schema

Edit `operator/api/v1alpha1/agentobservability_types.go`, regenerate CRD manifests (if using kubebuilder), update `manifests/crd/agentobservability-crd.yaml`.

### Testing runtime coordinator changes locally

You can test runtime coordinator outside Kubernetes by importing `agent_obs_runtime.bootstrap`:

```python
from agent_obs_runtime.bootstrap import bootstrap
bootstrap()
```

The coordinator will detect available frameworks and make instrumentation decisions automatically. Check stderr or `/tmp/runtime-coordinator-diagnostics.log` for diagnostic output.

## Debugging

### Operator not reconciling

Check operator logs for errors:
```bash
kubectl logs -n agent-observability-system deployment/agent-observability-operator -f
```

Verify CRD is installed:
```bash
kubectl get crd agentobservabilitydemos.platform.example.com
```

### Instrumentation not injected

Verify OTel Operator is running:
```bash
kubectl get pods -n opentelemetry-operator-system
```

Check if `Instrumentation` resource exists:
```bash
kubectl get instrumentation -n demo-apps
```

Verify Deployment annotations were added:
```bash
kubectl get deployment -n demo-apps agent-no-existing -o yaml | grep instrumentation
```

### Unexpected runtime coordinator decisions

Check coordinator startup diagnostics in pod logs. Look for JSON with event `detection_complete` containing `detection` and `decisions` objects.

Verify coordinator ConfigMap was created and mounted:
```bash
kubectl get configmap -n demo-apps | grep runtime
kubectl describe pod -n demo-apps <pod-name> | grep -A5 Mounts
```

### No traces in Jaeger

Verify Collector is receiving traces:
```bash
kubectl logs -n observability deployment/demo-collector-collector --tail=100
```

Send fresh traffic:
```bash
make send-demo-traffic
```

Check Jaeger pod is healthy:
```bash
kubectl get pods -n observability
```
