# Agent Observability Operator

A Kubernetes operator for Python observability with runtime-controlled auto-instrumentation.

## Overview

A Kubernetes operator that extends OpenTelemetry auto-instrumentation with runtime coordination for Python workloads. Platform teams configure observability via custom resources, while a runtime coordinator detects and respects existing application-owned tracing to avoid conflicts. Features a plugin architecture for extensible library support (FastAPI, httpx, requests, LangChain, MCP, OpenAI) with smart defaults and optional auto-detection.

## Quick Start

### Prerequisites

- Docker
- kind
- kubectl
- GNU make
- Ollama (for demo applications)

### Run the Demo

```bash
# One command for the full demo walkthrough
make demo-walkthrough

# Then port-forward Jaeger and open http://127.0.0.1:16686
make port-forward-jaeger
```

This creates a kind cluster, installs dependencies, builds images, deploys the operator and demo apps, and generates traces you can inspect in Jaeger.

**For detailed setup instructions, see [Quick Start Guide](docs/QUICKSTART.md).**

## Documentation

📚 **All documentation is in the [`docs/`](docs/) directory.**

- **[Quick Start Guide](docs/QUICKSTART.md)** - Build and run the demo from scratch
- **[Architecture](docs/ARCHITECTURE.md)** - System design, components, and data flow
- **[Configuration Guide](docs/CONFIGURATION.md)** - Configure custom resources
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Diagnose and fix common issues
- **[Plugin Development Guide](docs/PLUGIN_DEVELOPMENT.md)** - Add new instrumentation libraries

## Repository Structure

```
agent-observability-operator/
├── core/                      # Core solution components
│   ├── operator/             # Kubernetes operator (Go)
│   ├── runtime-coordinator/  # Python runtime policy engine
│   ├── custom-python-image/  # Custom Python auto-instrumentation image
│   ├── deploy/               # Core deployment manifests (CRD, operator RBAC)
│   └── scripts/              # Core build and deployment scripts
├── examples/                  # Demonstrations and samples
│   ├── end-to-end-demo/      # Complete demo (apps, manifests, scripts)
│   └── sample-configurations/ # Sample custom resources
├── docs/                      # All documentation
└── Makefile                   # Top-level build and demo targets
```

## What This PoC Demonstrates

End-to-end observability automation:

1. **Control Plane:** Custom operator reconciles custom resources into:
   - OpenTelemetry `Instrumentation` resources
   - Runtime coordinator `ConfigMap` configuration
   - Target workload annotations and environment variables

2. **Runtime Plane:** Custom Python auto-instrumentation image with coordinator that:
   - Detects existing tracing ownership at startup
   - Makes fine-grained per-library instrumentation decisions
   - Initializes TracerProvider only when needed
   - Emits structured diagnostics

3. **Data Plane:** Traces flow from instrumented apps → OpenTelemetry Collector → Jaeger

4. **Three Ownership Scenarios:**
   - `no-existing`: Platform owns everything (full auto-instrumentation)
   - `partial-existing`: Mixed ownership (app owns some, platform owns others)
   - `full-existing`: App owns everything (minimal platform instrumentation)

## Configuration Example

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-workload
spec:
  target:
    workloadName: my-deployment
    containerName: app
  instrumentation:
    # Smart defaults: enableInstrumentation and tracerProvider inferred
    fastapi: false      # App owns FastAPI instrumentation
    langchain: false    # App owns LangChain instrumentation
    # httpx, requests, mcp → default to true (platform owns)
```

**For complete configuration reference, see [Configuration Guide](docs/CONFIGURATION.md).**

## Development

### Build Commands

```bash
# Build operator
cd core/operator && go build -o bin/manager main.go

# Build all images
make build-images

# Run tests
cd core/operator && go test ./internal/controller/...
cd core/runtime-coordinator && python -m pytest tests/
```

### Adding a New Instrumentation Library

The system uses a plugin architecture. To add support for a new library:

1. Implement Python plugin in `core/runtime-coordinator/agent_obs_runtime/plugins/{library}.py`
2. Implement Go plugin in `core/operator/internal/controller/plugins/{library}.go`
3. Register plugins in both registries
4. Add CRD field to `core/operator/api/v1alpha1/agentobservability_types.go`
5. Run generation scripts

**For complete guide, see [Plugin Development Guide](docs/PLUGIN_DEVELOPMENT.md).**

## Known Limitations

This is a proof of concept, not a production-ready system:

- **Sitecustomize timing issue:** Coordinator runs before app's main.py, cannot detect what app will configure later
- **Deployment-only support:** Only patches Deployment workloads (not StatefulSets/DaemonSets)
- **Local kind cluster only:** Images built locally, not suitable for multi-node clusters
- **Simplified detection:** Uses heuristics rather than deep semantic analysis
- **Limited framework support:** FastAPI, httpx, requests, LangChain, MCP, OpenAI only
- **Ephemeral backend:** Jaeger uses in-memory storage, traces lost on restart

## Contributing

This is a proof of concept repository. Contributions should focus on:

- Improving the plugin architecture
- Adding support for new instrumentation libraries
- Enhancing runtime detection heuristics
- Fixing bugs in the demo

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## See Also

- [OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator)
- [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python)
- [OpenTelemetry Python Instrumentation](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation)
