# Core Components

This directory contains the core solution components of the agent observability operator system. These are the production-ready (or production-track) parts of the system, as opposed to demonstration or example code.

## Directory Structure

```
core/
├── operator/                    # Kubernetes operator (Go)
├── runtime-coordinator/         # Python runtime policy engine
├── custom-python-image/         # Custom Python auto-instrumentation Docker image
├── deploy/                      # Core deployment manifests
│   ├── crd/                    # AgentObservabilityDemo CRD definition
│   └── operator/               # Operator deployment, RBAC, and service account
└── scripts/                     # Core build and deployment scripts
    ├── build-core-images.sh    # Build operator and custom Python images
    ├── deploy-operator.sh      # Deploy operator to cluster
    └── check-operator-local.sh # Local operator validation
```

## Components

### Operator

**Location:** `operator/`

The Kubernetes operator reconciles `AgentObservabilityDemo` custom resources into:
- OpenTelemetry `Instrumentation` resources
- Runtime coordinator `ConfigMap` configuration
- Target workload patches (annotations, env vars, volume mounts)

**Key files:**
- `operator/main.go` - Operator entrypoint
- `operator/api/v1alpha1/` - CRD API types
- `operator/internal/controller/` - Reconciliation logic
- `operator/internal/controller/plugins/` - Plugin architecture

**See:** `operator/README.md` for implementation details.

### Runtime Coordinator

**Location:** `runtime-coordinator/`

The Python runtime policy engine that makes startup-time instrumentation decisions. Embedded in the custom Python auto-instrumentation image and invoked via `sitecustomize.py`.

**Key files:**
- `agent_obs_runtime/bootstrap.py` - Startup orchestration
- `agent_obs_runtime/instrumentation.py` - TracerProvider initialization
- `agent_obs_runtime/plugins/` - Plugin implementations

**See:** `runtime-coordinator/README.md` for implementation details.

### Custom Python Image

**Location:** `custom-python-image/`

Docker build assets for the custom Python auto-instrumentation image. This image:
- Packages OpenTelemetry core libraries and instrumentors
- Includes the runtime coordinator
- Uses `sitecustomize.py` to invoke coordinator at Python startup
- Delegates activation policy to the runtime coordinator

**Key files:**
- `Dockerfile` - Multi-stage build for custom image
- `src/sitecustomize.py` - Python startup hook
- `requirements.txt` - Auto-generated from plugin dependencies

**See:** `custom-python-image/README.md` for build details.

### Deployment Manifests

**Location:** `deploy/`

Kubernetes manifests required to deploy the core operator functionality.

**deploy/crd/**
- `agentobservability-crd.yaml` - Custom Resource Definition for AgentObservabilityDemo

**deploy/operator/**
- `deployment.yaml` - Operator Deployment
- `rbac.yaml` - ClusterRole and ClusterRoleBinding
- `serviceaccount.yaml` - ServiceAccount for operator

**Note:** Backend infrastructure (OpenTelemetry Collector, Jaeger) is **not** included here - those are demo/observability components located in `examples/`.

### Build and Deployment Scripts

**Location:** `scripts/`

Scripts for building, deploying, and maintaining core components.

**build-core-images.sh**
- Generates requirements.txt from plugin dependencies
- Builds operator image
- Builds custom Python auto-instrumentation image

**deploy-operator.sh**
- Applies CRD
- Applies operator RBAC and deployment
- Waits for operator to become ready

**check-operator-local.sh**
- Builds operator module
- Builds operator image
- Verifies operator manager process

**generate-plugin-fields.sh**
- Generates CRD fields from plugin registry
- Generates Go struct fields
- Updates both `autoinstrumentation_types_generated.go` and CRD YAML

**generate-requirements.py**
- Generates `requirements.txt` from plugin dependencies
- Collects dependencies from all registered plugins
- Automatically invoked by `build-core-images.sh`

## Building Core Images


```bash
# From repository root
core/scripts/build-core-images.sh
```

This builds:
- `agent-observability/operator:latest`
- `agent-observability/custom-python-autoinstrumentation:latest`

## Deploying the Operator

```bash
# From repository root
core/scripts/deploy-operator.sh
```

This deploys:
- AgentObservabilityDemo CRD
- Operator ServiceAccount, RBAC
- Operator Deployment

**Prerequisites:**
- Kubernetes cluster (kind, minikube, or any cluster)
- kubectl configured to access the cluster
- Core images built and available (locally or in registry)

**For local kind clusters:**
```bash
# Load images into kind after building
kind load docker-image agent-observability/operator:latest
kind load docker-image agent-observability/custom-python-autoinstrumentation:latest
```

## Using the Operator

Once deployed, create `AgentObservabilityDemo` custom resources to configure instrumentation:

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: my-agent
  namespace: my-namespace
spec:
  target:
    workloadName: my-deployment
    containerName: app
  instrumentation:
    enableInstrumentation: true
    # Configure per-library instrumentation...
```

**See:** [Configuration Guide](../docs/CONFIGURATION.md) for complete reference.

## Development

### Operator Development

```bash
cd core/operator

# Build locally
go build -o bin/manager main.go

# Run tests
go test ./internal/controller/...

# Build image
docker build -t agent-observability/operator:latest .
```

### Runtime Coordinator Development

```bash
cd core/runtime-coordinator

# Run tests
python -m pytest tests/

# Install locally for development
pip install -e .
```

### Adding a New Plugin

See [Plugin Development Guide](../docs/PLUGIN_DEVELOPMENT.md) for complete instructions.

## Dependencies

### Operator Dependencies

- Go 1.21+
- controller-runtime
- Kubernetes client-go
- OpenTelemetry Operator API

### Runtime Coordinator Dependencies

- Python 3.11+
- OpenTelemetry Python SDK
- Per-plugin instrumentor packages (auto-generated)

### Custom Python Image Dependencies

- Python 3.11-slim base image
- OpenTelemetry core packages
- Plugin-specific instrumentation packages

## See Also

- [Architecture](../docs/ARCHITECTURE.md) - System design and component interactions
- [Plugin Development Guide](../docs/PLUGIN_DEVELOPMENT.md) - Extending the system
- [Examples](../examples/README.md) - Demo applications and sample configurations (after refactoring)
