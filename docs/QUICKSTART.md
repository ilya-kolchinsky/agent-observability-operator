# Quick Start Guide

This guide will help you build and run the agent observability operator demo from scratch.

## Prerequisites

Install these locally before starting:

- Docker
- kind
- kubectl
- GNU make
- Ollama (for demo agents)

This PoC is designed around a **local kind cluster** and local Docker image builds.

## Fast Path: Full Demo Walkthrough

If you want the shortest path through the entire demo:

```bash
make demo-walkthrough
```

This command chains:
- Cluster creation
- Dependency installation (OpenTelemetry Operator, Collector, Jaeger)
- Image builds (operator, custom Python image, demo apps)
- Kind image loading
- Operator deployment
- Ollama setup (LLM for demo agents)
- Demo app deployment
- Sample CR application
- Verification
- Demo traffic generation

After completion, follow the instructions to port-forward Jaeger and inspect traces.

## Operator-Only Check

If you only want to validate the operator module locally before running the full PoC:

```bash
make operator-check-local
```

This builds the operator packages and image, and when a Kubernetes context is available it confirms the manager stays up long enough to catch basic regressions.

## Step-by-Step Manual Setup

If you want to understand and verify each phase manually, follow these steps.

### 1. Start a Local Kubernetes Cluster

```bash
make create-kind-cluster
kubectl get nodes
```

**Expected result:** A `kind-control-plane` node is `Ready` and your current `kubectl` context is `kind-kind`.

### 2. Install Dependencies

Install the OpenTelemetry Operator, the demo Collector, and Jaeger:

```bash
make install-deps
```

Or install them individually for explicit control:

```bash
make install-otel-operator
make install-collector
make install-jaeger
```

### 3. Build All Local Images

```bash
make build-images
```

This builds:
- The custom operator image
- The custom Python auto-instrumentation image
- The three demo agent images
- The mock MCP server image
- The mock external HTTP service image

### 4. Load Built Images into kind

```bash
make load-images-kind
```

### 5. Deploy the Custom Operator

```bash
make deploy-operator
kubectl get pods -n agent-observability-system
```

**Expected result:** The `agent-observability-operator` Deployment becomes `Available`.

### 6. Setup Ollama (for Demo Agents)

The demo agents use Ollama for LLM functionality. The setup script will:
- Check if Ollama is installed
- Start Ollama service if not running
- Download the phi model if not available

```bash
make setup-ollama
```

**Manual setup (alternative):**

```bash
# Install Ollama
# macOS:
brew install ollama

# Linux:
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama server (keep running in a separate terminal)
ollama serve

# Pull the phi model
ollama pull phi
```

### 7. Deploy the Demo Workloads

```bash
make deploy-demo-apps
kubectl get deployments -n demo-apps
```

**Expected result:** The three demo agent Deployments plus the two mock dependency Deployments are `Available`.

### 8. Apply the Sample Custom Resources

```bash
make apply-sample-crs
kubectl get autoinstrumentations -n demo-apps
```

**Expected result:** You see `no-existing`, `partial-existing`, and `full-existing`.

### 9. Verify Generated Instrumentation Resources

```bash
kubectl get instrumentation -n demo-apps
kubectl get instrumentation no-existing-instrumentation -n demo-apps
kubectl get instrumentation partial-existing-instrumentation -n demo-apps
kubectl get instrumentation full-existing-instrumentation -n demo-apps
```

These are created by the custom operator from the user-facing custom resources.

### 10. Verify Workload Mutation

Inspect one of the agent Pods:

```bash
kubectl get pods -n demo-apps
kubectl describe pod -n demo-apps <agent-pod-name>
```

Look for:
- `instrumentation.opentelemetry.io/inject-python`
- `instrumentation.opentelemetry.io/container-names`
- OTLP-related environment variables such as `OTEL_EXPORTER_OTLP_ENDPOINT`
- Injected auto-instrumentation details from the OpenTelemetry Operator
- Mounted runtime coordinator configuration

### 11. Run Automated Verification

```bash
make verify-demo
```

This verifies:
- The three custom resources exist
- The generated `Instrumentation` resources exist
- The operator logs show reconciliation activity
- The workload Pods were mutated
- The runtime coordinator made the expected instrumentation decisions
- Collector and Jaeger deployments are present

### 12. Send Demo Traffic

```bash
make send-demo-traffic
```

This exercises `/healthz`, `/run`, and `/stream` across the three demo services so traces appear in the backend.

### 13. Port-Forward Jaeger

```bash
make port-forward-jaeger
```

Then open `http://127.0.0.1:16686` in your browser.

## Demo Walkthrough Guide

Follow this sequence to understand the control-plane and runtime behavior.

### A. Observe Control-Plane Artifacts

After applying the sample CRs, confirm the custom resources and generated outputs:

```bash
kubectl get autoinstrumentations -n demo-apps -o wide
kubectl get instrumentation -n demo-apps -o wide
kubectl get configmap -n demo-apps | grep runtime
```

**What you're proving:**
- The user applied only `AutoInstrumentation` resources
- The operator generated the OpenTelemetry `Instrumentation` resources
- The operator generated runtime coordinator configuration

### B. Observe Workload Preparation

Inspect the demo Deployments and one Pod from each scenario:

```bash
kubectl get deployment -n demo-apps agent-no-existing -o yaml
kubectl get deployment -n demo-apps agent-partial-existing -o yaml
kubectl get deployment -n demo-apps agent-full-existing -o yaml
```

Then:

```bash
kubectl get pods -n demo-apps
kubectl describe pod -n demo-apps <pod-name>
```

**What you're proving:**
- The operator patched the target workload templates
- The OTel Operator mutated Pods for Python auto-instrumentation
- The Pods now have the config required to talk to the Collector

### C. Observe Runtime Coordinator Decisions

Check logs for each demo app:

```bash
kubectl logs -n demo-apps deployment/agent-no-existing --tail=200
kubectl logs -n demo-apps deployment/agent-partial-existing --tail=200
kubectl logs -n demo-apps deployment/agent-full-existing --tail=200
```

Look for startup diagnostics containing `detection_complete` with the `decisions` object.

The coordinator makes independent decisions for:
- `initialize_provider` - whether to initialize a TracerProvider
- `instrument_fastapi` - whether to instrument FastAPI
- `instrument_httpx` - whether to instrument httpx client
- `instrument_requests` - whether to instrument requests library
- `instrument_langchain` - whether to instrument LangChain (if available)
- `instrument_langgraph` - whether to instrument LangGraph
- `instrument_mcp` - whether to instrument MCP boundaries

### D. Generate Request Traffic

```bash
make send-demo-traffic
```

This triggers the demo agent workflow, which includes:
1. FastAPI ingress handling
2. LangGraph workflow execution
3. MCP tool calls to the mock MCP server
4. Outbound HTTP calls to the mock HTTP dependency
5. Response assembly back to the client

### E. Inspect Traces in Jaeger

After port-forwarding Jaeger, search for these services:
- `agent-no-existing`
- `agent-partial-existing`
- `agent-full-existing`

Open a recent trace for each service and compare both the trace shape and the coordinator behavior reflected in logs.

## Expected Results in Jaeger

The exact span names can vary by instrumentor version, but the visible pattern should be stable.

### 1. agent-no-existing

This is the cleanest demonstration of platform-owned observability.

**Expected traces:**
- A root server span for the FastAPI request (`/run` or `/stream`)
- Child spans representing outbound HTTP traffic to `mock-external-http-service`
- Spans or observable boundaries around MCP tool invocation activity
- LangGraph-related activity visible through runtime instrumentation
- A complete trace emitted through the Collector into Jaeger

**Interpretation:** The app had no meaningful existing tracing ownership, so the runtime coordinator initialized a provider and enabled all available instrumentations.

### 2. agent-partial-existing

This demonstrates coexistence with partial app-owned signals.

**Expected traces:**
- A root server span for the FastAPI request
- Outbound HTTP and other spans added by the coordinator
- Trace shape potentially similar to `no-existing`, depending on detection

**Interpretation:** The app includes tracing setup in its main.py, but the coordinator runs earlier at sitecustomize time.

### 3. agent-full-existing

This demonstrates app-owned tracing that the platform should ideally not override.

**Expected traces:**
- A root server span for the FastAPI request
- Outbound spans from HTTP clients
- Traces flowing successfully to the Collector and Jaeger

**Interpretation:** The application configures tracing in main.py, but this runs after sitecustomize where the coordinator makes decisions.

### Comparison Points

When comparing traces in Jaeger, focus on:
- Do all three services produce traces end to end?
- Does the coordinator make reasonable instrumentation decisions based on detected state?
- Are traces exported successfully to the collector and visible in Jaeger?

**Note:** Currently all three services show similar instrumentation decisions due to the sitecustomize timing issue - the coordinator runs before the application's main.py, so it cannot detect what the app will configure later. This architectural limitation is acknowledged and will be addressed in future iterations.

## Build Commands Reference

### Build Operator

```bash
cd operator
go build -o bin/manager main.go
```

### Build All Docker Images

```bash
make build-images
```

### Load Images into kind

```bash
make load-images-kind
```

### Run Operator Tests

```bash
cd operator
go test ./internal/controller/...
```

### Run Runtime Coordinator Tests

```bash
cd runtime-coordinator
python -m pytest tests/
```

## Cleanup

To tear down the demo environment:

```bash
make clean
```

This deletes the kind cluster and all local resources.
