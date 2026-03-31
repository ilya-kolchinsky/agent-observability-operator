# Operator

This module contains the custom Kubernetes operator responsible for reconciling the PoC custom resource into the supporting observability and demo workload resources.

## Workload preparation approach

For the current PoC, the operator prepares only `Deployment` targets. During reconciliation it:

- creates or updates an OpenTelemetry `Instrumentation` resource in the target namespace;
- creates or updates a runtime coordinator `ConfigMap` in the target namespace;
- patches the target Deployment pod template annotations so the OpenTelemetry Operator injects Python auto-instrumentation for the selected container; and
- patches only the selected container with the OTLP/service env vars plus a mounted runtime coordinator config file.

### Why ConfigMap-based coordinator config

The primary runtime coordinator configuration mechanism is a mounted `ConfigMap` file rather than encoding every coordinator setting directly into container environment variables. This keeps the coordinator configuration readable, easier to diff, and simpler to extend as the PoC grows, while still using a small env var surface to point the selected container at the mounted file.

## Real dependency model

The runnable operator now links against the real upstream Go modules for:

- `sigs.k8s.io/controller-runtime`
- `k8s.io/api`, `k8s.io/apimachinery`, and `k8s.io/client-go`
- `github.com/go-logr/logr`
- `github.com/open-telemetry/opentelemetry-operator`

Local stub replacements are no longer part of the runtime design. The controller manager process is expected to behave like a normal long-running `controller-runtime` manager, and the generated `Instrumentation` objects use the real OpenTelemetry Operator API types.

## Local verification

For a focused operator-only sanity check, run:

```bash
make operator-check-local
```

That helper builds the operator Go module with the real upstream dependencies, builds the operator image, and if a Kubernetes context is reachable, verifies that the manager process stays running for a short local check window.

