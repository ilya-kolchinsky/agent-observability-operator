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

## Prerequisites

### Ollama LLM (required for demo agents)

The demo agents use Ollama running locally on your host machine for better performance.

**Installation:**
Ollama must be installed before running the demo. Install it via:
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.com/download
```

**Automated Setup:**
The demo automatically checks if Ollama is running and if the required model (phi) is available.
If not, it will:
- Start the Ollama service automatically
- Download the phi model if needed

You can also manually run the setup:
```bash
make setup-ollama
```

The demo agents connect to Ollama at `http://host.docker.internal:11434` (which kind automatically maps to your host machine).

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
make deploy-demo-apps  # Ensure ollama is running first!
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

### Runtime coordinator decision logic (Plugin-Based)

The coordinator uses a **plugin architecture** where each instrumentation library is implemented as a plugin.
Plugins make independent decisions for each instrumentation target:

- **initialize_provider**: Initialize TracerProvider if only ProxyTracerProvider detected
- **Per-plugin instrumentation**: Each plugin decides whether to instrument based on config (true/false/"auto")
  - **Auto-detection plugins** (FastAPI, HTTPX, Requests): Support runtime ownership resolution
  - **Explicit-only plugins** (LangChain, MCP): Require explicit true/false configuration

### Operator code structure (Plugin-Based)

- `operator/main.go` - operator entrypoint, manager setup
- `operator/api/v1alpha1/agentobservability_types.go` - CRD API types (AgentObservabilityDemo spec/status)
- `operator/internal/controller/agentobservability_controller.go` - reconciliation logic (plugin-driven)
- `operator/internal/controller/plugins/` - plugin implementations:
  - `plugin.go` - InstrumentationPlugin interface
  - `registry.go` - explicit plugin registry
  - `{library}.go` - per-library plugins (fastapi, httpx, requests, langchain, mcp)
  - `common/helpers.go` - shared type checking/conversion utilities
- `operator/stubs/` - type stubs for k8s and OTel Operator APIs (used instead of full dependencies)
- `scripts/generate-plugin-fields.sh` - generates CRD fields from plugin registry

### Runtime coordinator structure (Plugin-Based)

- `runtime-coordinator/agent_obs_runtime/bootstrap.py` - startup orchestration (plugin-driven)
- `runtime-coordinator/agent_obs_runtime/instrumentation.py` - TracerProvider initialization only
- `runtime-coordinator/agent_obs_runtime/plugins/` - plugin implementations:
  - `base.py` - InstrumentationPlugin abstract base class
  - `registry.py` - explicit plugin registry
  - `{library}.py` - per-library plugins (fastapi, httpx, requests, langchain, mcp)
  - `common/` - shared utilities:
    - `ownership.py` - OwnershipResolver state machine
    - `wrapper_utils.py` - thread-local context, diagnostics
    - `detection_utils.py` - library availability/instrumentation checks
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

**Target specification:**
- `spec.target.namespace` - target workload namespace (optional, defaults to CR namespace)
- `spec.target.workloadName` - target workload name (required)
- `spec.target.workloadKind` - target workload kind (optional, defaults to "Deployment")
- `spec.target.containerName` - target container name within the workload (required)

**Instrumentation configuration:**
- `spec.instrumentation.customPythonImage` - custom auto-instrumentation image reference (optional, defaults to `agent-observability/custom-python-autoinstrumentation:latest`)
- `spec.instrumentation.otelCollectorEndpoint` - OTLP endpoint for traces (optional, defaults to `http://agent-observability-collector.observability.svc.cluster.local:4318`)

**Smart defaults with inference:**

- `spec.instrumentation.enableInstrumentation` (optional)
  - `true` - enable auto-instrumentation with library defaults
  - `false` - disable all auto-instrumentation (safety override)
  - **If omitted and other instrumentation fields are specified → defaults to `true`** (implicit opt-in)
  - **If omitted and no instrumentation fields specified → defaults to `false`** (safe for production)

- `spec.instrumentation.tracerProvider` (optional)
  - `platform` - coordinator initializes TracerProvider
  - `app` - app owns TracerProvider initialization
  - **If omitted, inferred from library field values:**
    - All library fields `true` (or default) → `platform`
    - At least one library field `false` → `app`

- `spec.instrumentation.{fastapi,httpx,requests,langchain,mcp}` (optional boolean)
  - `true` - platform instruments this library
  - `false` - app instruments this library (opt-out)
  - **If omitted and `enableInstrumentation` is true → defaults to `true`**
  - **If omitted and `enableInstrumentation` is false → defaults to `false`**

**Validation:**

The operator validates for contradictory configuration and will reject the CR with an error if:
- `enableInstrumentation: false` AND any library field is explicitly set to `true`

This prevents ambiguous configurations. If you want to disable auto-instrumentation, all explicit library fields must be `false` (or omitted).

### Configuration patterns

**Pattern 1: Full auto-instrumentation (demo/development)**
```yaml
spec:
  instrumentation:
    enableInstrumentation: true
# All libs → true, tracerProvider → platform
```

**Pattern 2: Selective opt-out (partial existing instrumentation)**
```yaml
spec:
  instrumentation:
    fastapi: false      # App instruments FastAPI
    langchain: false    # App instruments LangChain
# enableInstrumentation → true (implicit)
# Other libs → true, tracerProvider → app (inferred)
```

**Pattern 3: Minimal instrumentation (full existing setup)**
```yaml
spec:
  instrumentation:
    fastapi: false
    httpx: false
    requests: false
    langchain: false
    mcp: false
# enableInstrumentation → true (implicit)
# tracerProvider → app (inferred)
```

**Pattern 4: Production safe default (no config)**
```yaml
spec:
  instrumentation: {}
# enableInstrumentation → false (safe default)
# No instrumentation applied
```

**Pattern 5: Explicit control (override inference)**
```yaml
spec:
  instrumentation:
    enableInstrumentation: true
    tracerProvider: app      # Override inference
    langchain: false
    fastapi: true
```

## Important Constraints

- **Operator only patches Deployment workloads** in this PoC (not StatefulSets/DaemonSets)
- **Operator uses ConfigMap-based coordinator config** rather than encoding everything in env vars
- **Runtime coordinator is PoC-focused** with simplified heuristics, not production-grade semantic analysis
- **Supported Python frameworks**: FastAPI, ASGI, httpx, requests, MCP boundaries, LangChain
- **Ollama runs on host machine** - demo agents connect to `http://host.docker.internal:11434` for better LLM performance
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

### Adding a new instrumentation plugin

The operator uses a **plugin architecture** for extensibility. To add support for a new library:

1. **Implement Python plugin** in `runtime-coordinator/agent_obs_runtime/plugins/{library}.py`
2. **Implement Go plugin** in `operator/internal/controller/plugins/{library}.go`
3. **Register plugins** in both `registry.py` and `registry.go`
4. **Add CRD field** to `operator/api/v1alpha1/agentobservability_types.go`
5. **Update helper functions** in `agentobservability_controller.go` (getPluginFieldValue/setPluginFieldValue)
6. **Run generation script**: `scripts/generate-plugin-fields.sh` to update CRD YAML

See **[docs/PLUGIN_DEVELOPMENT.md](docs/PLUGIN_DEVELOPMENT.md)** for a complete guide with examples.

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

### Agent pods failing to start or timing out

Check if Ollama is running and reachable:
```bash
# Verify Ollama is running locally
curl http://localhost:11434/api/tags

# Check agent logs for connection errors
kubectl logs -n demo-apps deployment/agent-no-existing --tail=50
```

If Ollama is not running or model is missing, run the setup script:
```bash
make setup-ollama
```

This will automatically start Ollama and download the phi model if needed.
