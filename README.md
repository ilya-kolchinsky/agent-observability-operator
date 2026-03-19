# agent-observability-operator

This proof-of-concept repository explores how a standalone Kubernetes operator can simplify OpenTelemetry-based auto-instrumentation for Python agent workloads. The goal is to give users a single custom resource that describes an agent deployment and lets the platform generate the supporting observability components, image conventions, and runtime behavior needed to capture traces with minimal manual setup.

The planned architecture centers on a custom operator that watches a user-facing custom resource and reconciles the resources required for the demo environment. Those resources include generated OpenTelemetry Instrumentation objects, a custom Python auto-instrumentation image with an embedded runtime coordinator, demo Python agent applications, an OpenTelemetry Collector, and a Jaeger backend for trace storage and visualization, all packaged with local Kubernetes manifests and helper scripts.

This PoC validates the deployment model and repository structure while also proving a key runtime idea: the image can ship instrumentation packages, but a coordinator inside the container still decides which instrumentors are actually activated at startup.

## Runtime coordinator at a glance

The runtime coordinator lives in `runtime-coordinator/` and is the policy engine for Python observability in this PoC.

At process startup it:

1. Loads runtime configuration from environment variables and an optional config file.
2. Detects whether the application already appears to own tracing setup.
3. Selects a coordination mode: `FULL`, `AUGMENT`, `REUSE_EXISTING`, or `OFF`.
4. Builds an instrumentation plan describing what should be activated.
5. Applies that plan safely and logs both selected mode and actions taken.

Today the coordinator supports:

- provider ownership heuristics based on tracer providers, processors/exporters, environment signals, and known framework tracing indicators
- runtime activation control for FastAPI/ASGI ingress and `httpx`/`requests` egress
- lightweight MCP wrapper activation for representative tool-call boundaries
- optional LangChain and LangGraph activation paths when compatible packages are present
- structured startup diagnostics describing detection, plan, and applied actions

For implementation details and extension points, see `runtime-coordinator/README.md`.

## Local dependency layer for the demo

The current demo dependency path is:

```text
app -> OTLP -> Collector -> Jaeger UI
```

This phase adds the Kubernetes-side dependencies needed for that path without yet wiring the custom operator into them.

### What gets installed

- **OpenTelemetry Operator** via raw upstream manifests applied by `kubectl` from `scripts/install-otel-operator.sh`.
- **OpenTelemetry Collector** via `manifests/collector/collector.yaml`, running as a single demo instance managed by the OpenTelemetry Operator.
- **Jaeger all-in-one** via `manifests/jaeger/jaeger.yaml`, with a ClusterIP service for the Jaeger UI and OTLP ingest ports enabled for the Collector.

### Local demo install order

A local kind cluster is the preferred target environment, though the scripts work against any current `kubectl` context.

```bash
make install-deps
```

Or install each dependency explicitly:

```bash
make install-otel-operator
make install-jaeger
make install-collector
```

After installation, port-forward the UI locally if needed:

```bash
kubectl port-forward -n observability svc/jaeger-query 16686:16686
```

Then point instrumented apps at the Collector OTLP endpoint inside the cluster:

- gRPC: `demo-collector-collector.observability.svc.cluster.local:4317`
- HTTP: `http://demo-collector-collector.observability.svc.cluster.local:4318`

## Repository layout

- `operator/` - Custom Kubernetes operator skeleton.
- `runtime-coordinator/` - Python runtime policy engine that detects tracing ownership, selects a mode, builds an instrumentation plan, and activates supported instrumentation.
- `custom-python-image/` - Docker image skeleton for Python auto-instrumentation and runtime coordinator integration.
- `demo-apps/` - Example Python agent applications used in the PoC.
- `manifests/` - Kubernetes manifests organized by component.
- `scripts/` - Local workflow helper scripts.
