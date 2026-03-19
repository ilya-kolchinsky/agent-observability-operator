# agent-observability-operator

This proof-of-concept repository explores how a standalone Kubernetes operator can simplify OpenTelemetry-based auto-instrumentation for Python agent workloads. The goal is to give users a single custom resource that describes an agent deployment and lets the platform generate the supporting observability components, image conventions, and runtime behavior needed to capture traces with minimal manual setup.

The planned architecture centers on a custom operator that watches a user-facing custom resource and reconciles the resources required for the demo environment. Those resources include generated OpenTelemetry Instrumentation objects, a custom Python auto-instrumentation image with an embedded runtime coordinator, demo Python agent applications, an OpenTelemetry Collector, and a Jaeger backend for trace storage and visualization, all packaged with local Kubernetes manifests and helper scripts.

This PoC will prove that we can present a clean Kubernetes-native API for instrumenting Python agent applications end to end while retaining control over the runtime image and orchestration flow. It is intended to validate the repository structure, deployment model, and developer workflow before implementation details are added for reconciliation logic, runtime behavior, telemetry pipelines, and example applications.

## Repository layout

- `operator/` - Custom Kubernetes operator skeleton.
- `runtime-coordinator/` - Placeholder runtime process for the custom Python image.
- `custom-python-image/` - Docker image skeleton for Python auto-instrumentation.
- `demo-apps/` - Example Python agent applications used in the PoC.
- `manifests/` - Kubernetes manifests organized by component.
- `scripts/` - Local workflow helper scripts.
