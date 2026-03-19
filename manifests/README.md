# Manifests

This directory contains the Kubernetes resources for the end-to-end PoC:

- `crd/` - the `AgentObservabilityDemo` CRD
- `operator/` - the custom operator Deployment and RBAC
- `collector/` - the OpenTelemetry Collector custom resource plus a stable Collector service alias
- `jaeger/` - the Jaeger all-in-one Deployment and UI / OTLP services
- `demo/` - the demo app Deployments and stable Services
- `samples/` - three sample `AgentObservabilityDemo` resources (`no-existing`, `partial-existing`, `full-existing`)
