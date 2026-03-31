# Examples

This directory contains demonstrations and sample configurations for the agent observability operator.

## Directory Structure

```
examples/
├── end-to-end-demo/           # Complete end-to-end demonstration
│   ├── apps/                 # Demo applications (3 agent variants + mocks)
│   ├── manifests/           # Demo infrastructure manifests
│   └── scripts/             # Demo automation scripts
└── sample-configurations/    # Sample AgentObservabilityDemo CRs
```

## End-to-End Demo

**Location:** `end-to-end-demo/`

A complete, runnable demonstration that shows:
- How to deploy the operator
- Three instrumentation ownership scenarios (no-existing, partial-existing, full-existing)
- Runtime coordinator decision-making
- Trace collection and visualization in Jaeger

**Quick start:**
```bash
# From repository root
make demo-walkthrough
```

**See:** `end-to-end-demo/README.md` for detailed walkthrough.

## Sample Configurations

**Location:** `sample-configurations/`

Example `AgentObservabilityDemo` custom resources demonstrating different configuration patterns:

- **no-existing** - Full platform-owned instrumentation
- **partial-existing** - Mixed ownership (app owns some, platform owns others)
- **full-existing** - App owns all instrumentation

**See:** `sample-configurations/README.md` for complete examples and explanations.

## Using These Examples

### Run the Full Demo

The end-to-end demo provides the fastest way to see the system in action:

```bash
# One command for complete demo setup
make demo-walkthrough
```

This will:
1. Create a local kind cluster
2. Install dependencies (OpenTelemetry Operator, Collector, Jaeger)
3. Build all images (operator, custom Python image, demo apps)
4. Load images into kind
5. Deploy the operator
6. Setup Ollama (LLM for demo agents)
7. Deploy demo applications
8. Apply sample CRs
9. Verify instrumentation
10. Generate demo traffic

After completion, port-forward Jaeger and inspect traces:

```bash
make port-forward-jaeger
# Open http://127.0.0.1:16686
```

### Try Different Configurations

Apply sample CRs individually to experiment with different configurations:

```bash
# Apply a specific sample
kubectl apply -f examples/sample-configurations/agentobservability-sample.yaml

# Or create your own
cat <<EOF | kubectl apply -f -
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: my-test
  namespace: my-namespace
spec:
  target:
    workloadName: my-deployment
    containerName: app
  instrumentation:
    enableInstrumentation: true
    fastapi: false  # App owns FastAPI
EOF
```

### Study the Demo Apps

The demo applications (`end-to-end-demo/apps/`) show three different instrumentation scenarios:

1. **agent-no-existing:** No tracing setup in application code
2. **agent-partial-existing:** Some tracing configured by app
3. **agent-full-existing:** Full tracing owned by app

Compare their `main.py` files to see the differences in application-side configuration.

## What to Learn From These Examples

### Configuration Patterns

The sample configurations demonstrate:
- **Smart defaults and inference** - Minimal config with intelligent defaults
- **Explicit configuration** - Fine-grained control when needed
- **Auto-detection** - Runtime ownership resolution
- **Validation** - What the operator will accept/reject

**See:** [Configuration Guide](../docs/CONFIGURATION.md) for complete reference.

### Runtime Coordinator Behavior

The demo apps show how the runtime coordinator:
- Detects existing instrumentation
- Makes per-library decisions
- Initializes TracerProvider when needed
- Emits structured diagnostics

Check pod logs for coordinator startup diagnostics:

```bash
kubectl logs -n demo-apps deployment/agent-no-existing --tail=200 | grep detection_complete
```

### Trace Visualization

The demo includes Jaeger to visualize traces:
- Compare traces across the three scenarios
- See which spans come from platform vs app instrumentation
- Observe the complete request flow (FastAPI → LangGraph → MCP → HTTP)

## Prerequisites for Running Examples

- Docker
- kind (Kubernetes in Docker)
- kubectl
- GNU make
- Ollama (for demo agents with LLM functionality)

**Installation:**

```bash
# macOS
brew install docker kind kubectl make ollama

# Linux (example for Ubuntu)
# Docker: https://docs.docker.com/engine/install/
# kind: https://kind.sigs.k8s.io/docs/user/quick-start/
# kubectl: https://kubernetes.io/docs/tasks/tools/
# Ollama: https://ollama.com/download
```

## Customizing the Examples

### Modify Demo Apps

Edit files in `end-to-end-demo/apps/` to experiment with different:
- Application-side instrumentation
- LangGraph workflows
- MCP tool implementations

After changes, rebuild and redeploy:

```bash
make build-images
make load-images-kind
kubectl delete pod -n demo-apps -l app.kubernetes.io/component=agent
```

### Modify Sample CRs

Create new sample configurations to test different scenarios:

```bash
cp examples/sample-configurations/agentobservability-sample.yaml my-test.yaml
# Edit my-test.yaml with your configuration
kubectl apply -f my-test.yaml
```

### Add New Demo Apps

To add a new demo application:

1. Create app directory in `end-to-end-demo/apps/`
2. Add Dockerfile
3. Update `end-to-end-demo/manifests/demo/` with Deployment/Service
4. Update `scripts/build-images.sh` to build the new image
5. Create corresponding sample CR in `sample-configurations/`

## Cleanup

To tear down the demo environment:

```bash
make clean
```

This deletes the kind cluster and all local resources.

## See Also

- [Quick Start Guide](../docs/QUICKSTART.md) - Detailed setup instructions
- [Architecture](../docs/ARCHITECTURE.md) - System design and components
- [Configuration Guide](../docs/CONFIGURATION.md) - CR configuration reference
- [Troubleshooting](../docs/TROUBLESHOOTING.md) - Common issues and solutions
