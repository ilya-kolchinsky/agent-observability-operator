# End-to-End Demo

This directory contains a complete, self-contained demonstration of the agent observability operator system.

## What This Demo Shows

This demo demonstrates the entire system end-to-end:

1. **Three instrumentation ownership scenarios:**
   - `agent-no-existing`: Platform owns everything (full auto-instrumentation)
   - `agent-partial-existing`: Mixed ownership (app owns some, platform owns others)
   - `agent-full-existing`: App owns everything (minimal platform instrumentation)

2. **Runtime coordinator decision-making:**
   - How the coordinator detects existing instrumentation
   - Per-library instrumentation decisions
   - TracerProvider initialization logic

3. **Complete observability stack:**
   - Agent apps emit traces
   - OpenTelemetry Collector receives and processes traces
   - Jaeger stores and visualizes traces

4. **Real agent workload:**
   - FastAPI HTTP ingress
   - LangGraph workflow execution
   - MCP tool calls
   - Outbound HTTP requests
   - Ollama LLM integration

## Directory Structure

```
end-to-end-demo/
├── apps/                          # Demo applications
│   ├── agent-no-existing/        # No tracing in app code
│   ├── agent-partial-existing/   # Partial app-owned tracing
│   ├── agent-full-existing/      # Full app-owned tracing
│   ├── common/                   # Shared agent implementation
│   ├── mcp-server/               # Mock MCP server
│   └── README.md                 # Demo apps documentation
├── manifests/                     # Kubernetes manifests
│   ├── otel-operator/            # OpenTelemetry Operator installation
│   ├── collector/                # OTel Collector deployment
│   ├── jaeger/                   # Jaeger all-in-one deployment
│   └── demo/                     # Demo app deployments
└── scripts/                       # Automation scripts
    ├── demo.sh                   # Full demo walkthrough
    ├── create-kind-cluster.sh    # Create local kind cluster
    ├── install-deps.sh           # Install OTel Operator, Collector, Jaeger
    ├── setup-ollama.sh           # Setup Ollama LLM
    ├── deploy-demo-apps.sh       # Deploy demo applications
    ├── apply-sample-crs.sh       # Apply sample CRs
    ├── verify-demo.sh            # Verify instrumentation
    ├── send-demo-traffic.sh      # Generate demo traffic
    ├── port-forward-jaeger.sh    # Port-forward Jaeger UI
    └── clean.sh                  # Tear down demo environment
```

## Quick Start

### Option 1: One-Command Demo

From the repository root:

```bash
make demo-walkthrough
```

This runs the complete demo setup automatically.

### Option 2: Step-by-Step

For a more hands-on experience:

```bash
# 1. Create kind cluster
examples/end-to-end-demo/scripts/create-kind-cluster.sh

# 2. Install dependencies
examples/end-to-end-demo/scripts/install-deps.sh

# 3. Build all images
make build-images

# 4. Load images into kind
examples/end-to-end-demo/scripts/load-images-kind.sh

# 5. Deploy operator
core/scripts/deploy-operator.sh

# 6. Setup Ollama
examples/end-to-end-demo/scripts/setup-ollama.sh

# 7. Deploy demo apps
examples/end-to-end-demo/scripts/deploy-demo-apps.sh

# 8. Apply sample CRs
examples/end-to-end-demo/scripts/apply-sample-crs.sh

# 9. Verify instrumentation
examples/end-to-end-demo/scripts/verify-demo.sh

# 10. Send demo traffic
examples/end-to-end-demo/scripts/send-demo-traffic.sh

# 11. Port-forward Jaeger and open http://127.0.0.1:16686
examples/end-to-end-demo/scripts/port-forward-jaeger.sh
```

## Demo Applications

### Three Agent Scenarios

All three agents share the same workload implementation (FastAPI + LangGraph + MCP + httpx) but differ in their tracing setup:

**agent-no-existing (`apps/agent-no-existing/`)**
- No tracing configured in `main.py`
- Platform coordinator initializes TracerProvider
- Platform instruments all available libraries
- Demonstrates full platform-owned observability

**agent-partial-existing (`apps/agent-partial-existing/`)**
- App configures TracerProvider in `main.py`
- App configures some instrumentation (LangChain)
- Platform instruments remaining libraries (httpx, requests, MCP)
- Demonstrates mixed ownership with `autoDetection: true`

**agent-full-existing (`apps/agent-full-existing/`)**
- App configures TracerProvider in `main.py`
- App instruments all libraries
- Platform respects app's ownership
- Demonstrates full app-owned observability

### Shared Implementation

All three agents share the same core functionality:

**common/ directory:**
- `agent_app.py` - LangGraph workflow, MCP client, HTTP calls, Ollama integration
- `logging_config.py` - Structured logging setup
- `tracing.py` - Tracing utilities and helpers

This ensures the demo focuses on **instrumentation ownership differences** rather than application behavior differences.

### Mock Dependencies

**mcp-server (`apps/mcp-server/`)**
- Simple MCP server implementing tool boundaries
- Demonstrates platform instrumentation of MCP calls

**Note:** The demo also includes a mock external HTTP service (not using MCP) to show outbound HTTP instrumentation.

## Observability Stack

### OpenTelemetry Collector

**Location:** `manifests/collector/`

Receives OTLP traces from instrumented apps and exports to Jaeger.

**Endpoint:** `demo-collector-collector.observability.svc.cluster.local:4318`

**Configuration:**
- OTLP HTTP receiver on port 4318
- OTLP gRPC receiver on port 4317
- Jaeger exporter

### Jaeger

**Location:** `manifests/jaeger/`

All-in-one Jaeger deployment for trace storage and visualization.

**UI Access:**
```bash
examples/end-to-end-demo/scripts/port-forward-jaeger.sh
# Open http://127.0.0.1:16686
```

**Note:** Uses in-memory storage - traces are lost when Jaeger restarts.

### Ollama

The demo agents use Ollama running **on your host machine** for LLM functionality. This is faster and more reliable than running Ollama in the cluster.

**Setup:**
```bash
# Automated setup (preferred)
examples/end-to-end-demo/scripts/setup-ollama.sh

# Manual setup
ollama serve  # Keep running
ollama pull phi
```

Agents connect to Ollama at `http://host.docker.internal:11434` (kind automatically maps this to your host).

## Verification

### Check Operator Reconciliation

```bash
kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
kubectl get agentobservabilitydemos -n demo-apps
kubectl get instrumentation -n demo-apps
```

### Check Runtime Coordinator Decisions

```bash
kubectl logs -n demo-apps deployment/agent-no-existing --tail=200 | grep detection_complete
kubectl logs -n demo-apps deployment/agent-partial-existing --tail=200 | grep detection_complete
kubectl logs -n demo-apps deployment/agent-full-existing --tail=200 | grep detection_complete
```

Or check the diagnostics file:

```bash
kubectl exec -n demo-apps deployment/agent-no-existing -- cat /tmp/runtime-coordinator-diagnostics.log
```

### Check Traces in Jaeger

After port-forwarding Jaeger:

1. Open http://127.0.0.1:16686
2. Select service: `agent-no-existing`, `agent-partial-existing`, or `agent-full-existing`
3. Click "Find Traces"
4. Click on a trace to see detailed span tree

**Compare:**
- Trace shape across the three scenarios
- Span names and attributes
- Instrumentation source (platform vs app)

## Traffic Generation

The demo includes a traffic generation script that exercises all agent endpoints:

```bash
examples/end-to-end-demo/scripts/send-demo-traffic.sh
```

This sends:
- Health check requests (`/healthz`)
- Synchronous workflow requests (`/run`)
- Streaming workflow requests (`/stream`)

To generate continuous traffic:

```bash
while true; do examples/end-to-end-demo/scripts/send-demo-traffic.sh; sleep 10; done
```

## Customizing the Demo

### Modify Agent Behavior

Edit files in `apps/common/` to change the shared agent implementation:

```bash
# Edit the LangGraph workflow
vim apps/common/agent_app.py

# Rebuild images
make build-images
examples/end-to-end-demo/scripts/load-images-kind.sh

# Recreate pods
kubectl delete pod -n demo-apps -l app.kubernetes.io/component=agent
```

### Try Different Configurations

Modify the sample CRs in `../sample-configurations/` and reapply:

```bash
vim ../sample-configurations/agentobservability-sample.yaml
kubectl apply -f ../sample-configurations/agentobservability-sample.yaml
```

### Change Instrumentation Decisions

Edit the CR for a specific agent:

```bash
kubectl edit agentobservabilitydemo no-existing -n demo-apps
```

The operator will reconcile the change and update the Instrumentation resource.

## Cleanup

To tear down the entire demo:

```bash
examples/end-to-end-demo/scripts/clean.sh
```

Or from repository root:

```bash
make clean
```

This deletes the kind cluster and all resources.

## Troubleshooting

### Demo Walkthrough Fails

Check which step failed and refer to the [Troubleshooting Guide](../../docs/TROUBLESHOOTING.md).

Common issues:
- **Ollama not running:** Run `examples/end-to-end-demo/scripts/setup-ollama.sh`
- **Images not loaded:** Run `examples/end-to-end-demo/scripts/load-images-kind.sh`
- **Pods not mutated:** Check operator logs and verify CRs applied

### No Traces in Jaeger

1. Re-send traffic: `examples/end-to-end-demo/scripts/send-demo-traffic.sh`
2. Check Collector logs: `kubectl logs -n observability deployment/demo-collector-collector`
3. Check app logs: `kubectl logs -n demo-apps deployment/agent-no-existing`

### Coordinator Not Starting

1. Check pod logs for errors: `kubectl logs -n demo-apps deployment/agent-no-existing --tail=100`
2. Verify ConfigMap mounted: `kubectl describe pod -n demo-apps <pod-name>`
3. Verify custom image loaded: `docker images | grep custom-python-autoinstrumentation`

## See Also

- [Quick Start Guide](../../docs/QUICKSTART.md) - Complete setup documentation
- [Architecture](../../docs/ARCHITECTURE.md) - System design details
- [Configuration Guide](../../docs/CONFIGURATION.md) - CR configuration reference
- [Troubleshooting Guide](../../docs/TROUBLESHOOTING.md) - Detailed troubleshooting
- [Sample Configurations](../sample-configurations/README.md) - More CR examples
