# agent-observability-operator

This repository is a standalone end-to-end PoC for Python agent observability on Kubernetes. It includes:

- a custom `AgentObservabilityDemo` CRD and operator that prepare workloads for OpenTelemetry injection;
- a runtime coordinator embedded in a custom Python auto-instrumentation image;
- three demo FastAPI agent apps representing `no-existing`, `partial-existing`, and `full-existing` tracing ownership states;
- mock downstream MCP and HTTP services to generate realistic spans; and
- local manifests plus helper scripts that wire the full trace path from app -> Collector -> Jaeger.

## End-to-end telemetry path

```text
agent app
  -> OTLP HTTP (agent-observability-collector.observability.svc.cluster.local:4318)
  -> OpenTelemetry Collector
  -> Jaeger collector
  -> Jaeger UI (agent-observability-jaeger.observability.svc.cluster.local:16686)
```

## Stable service names

- Collector: `agent-observability-collector.observability.svc.cluster.local`
- Jaeger UI: `agent-observability-jaeger.observability.svc.cluster.local`
- Demo apps:
  - `agent-no-existing.demo-apps.svc.cluster.local`
  - `agent-partial-existing.demo-apps.svc.cluster.local`
  - `agent-full-existing.demo-apps.svc.cluster.local`
  - `mock-mcp-server.demo-apps.svc.cluster.local`
  - `mock-external-http-service.demo-apps.svc.cluster.local`

## Demo walkthrough

The most direct end-to-end path is:

```bash
make demo-walkthrough
```

That script chains the full local demo up through traffic generation, then tells you how to open Jaeger. If you want to walk the PoC step by step and verify each stage with your own eyes, use the commands below.

### 1. Start a local Kubernetes cluster with kind

```bash
make create-kind-cluster
kubectl get nodes
```

Expected result: a `kind-control-plane` node is `Ready` and your current kubectl context is `kind-kind`.

### 2. Install dependencies

Install the OpenTelemetry Operator, the demo Collector, and Jaeger:

```bash
make install-deps
```

If you prefer the explicit order used by the walkthrough:

```bash
make install-otel-operator
make install-collector
make install-jaeger
```

### 3. Build and load images

```bash
make build-images
make load-images-kind
```

### 4. Deploy the custom operator

```bash
make deploy-operator
kubectl get pods -n agent-observability-system
```

Expected result: the `agent-observability-operator` Deployment is `Available`.

### 5. Deploy the demo app variants

```bash
make deploy-demo-apps
kubectl get deployments -n demo-apps
```

Expected result: the three agent Deployments plus the two mock dependency Deployments are `Available`.

### 6. Apply the custom resources

```bash
make apply-sample-crs
kubectl get agentobservabilitydemos -n demo-apps
```

Expected result: you see `no-existing`, `partial-existing`, and `full-existing`.

### 7. Verify the generated `Instrumentation` resources exist

```bash
kubectl get instrumentation -n demo-apps
kubectl get instrumentation no-existing-instrumentation -n demo-apps
kubectl get instrumentation partial-existing-instrumentation -n demo-apps
kubectl get instrumentation full-existing-instrumentation -n demo-apps
```

You can also run the automated verification helper:

```bash
make verify-demo
```

### 8. Verify the workload Pods were mutated for auto-instrumentation

Inspect one of the agent Pods:

```bash
kubectl get pods -n demo-apps
kubectl describe pod -n demo-apps <agent-pod-name>
```

Look for all of the following:

- the `instrumentation.opentelemetry.io/inject-python` annotation;
- the `instrumentation.opentelemetry.io/container-names` annotation;
- OpenTelemetry-related environment such as `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`; and
- auto-instrumentation-related init container or injected instrumentation details from the OpenTelemetry Operator.

The helper target performs these checks for all three agent variants:

```bash
make verify-demo
```

### 9. Send traffic to the demo agent endpoint

```bash
make send-demo-traffic
```

That script exercises `healthz`, `run`, and `stream` against all three demo agent services so there is data to inspect in the backend.

### 10. Port-forward the Jaeger UI

```bash
make port-forward-jaeger
```

Then open `http://127.0.0.1:16686` in your browser.

### 11. Open Jaeger and inspect traces

In Jaeger:

1. Search for the services `agent-no-existing`, `agent-partial-existing`, and `agent-full-existing`.
2. Open a recent trace.
3. Confirm the trace includes app spans plus downstream HTTP and MCP-related activity.
4. Compare how the three services behave after the runtime coordinator chooses different ownership modes.

Optional cross-checks from the cluster side:

```bash
kubectl logs -n observability deployment/demo-collector-collector --tail=200
kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
```

### 12. Observe logs showing the runtime coordinator selected `FULL`, `AUGMENT`, and `REUSE_EXISTING`

Check each demo app directly:

```bash
kubectl logs -n demo-apps deployment/agent-no-existing --tail=200
kubectl logs -n demo-apps deployment/agent-partial-existing --tail=200
kubectl logs -n demo-apps deployment/agent-full-existing --tail=200
```

Look for the runtime coordinator JSON startup summary containing `selected_mode`.

Expected mapping:

- `agent-no-existing` -> `FULL`
- `agent-partial-existing` -> `AUGMENT`
- `agent-full-existing` -> `REUSE_EXISTING`

The helper target verifies this mapping automatically:

```bash
make verify-demo
```

## Troubleshooting

### No traces arriving in Jaeger

- Re-run `make send-demo-traffic` so fresh spans are generated.
- Check Collector logs for OTLP receive/export activity:

  ```bash
  kubectl logs -n observability deployment/demo-collector-collector --tail=200
  ```

- Confirm the injected app configuration still points at `http://agent-observability-collector.observability.svc.cluster.local:4318`.
- Make sure Jaeger is healthy:

  ```bash
  kubectl get pods -n observability
  kubectl logs -n observability deployment/jaeger --tail=200
  ```

### Pod not mutated

- Confirm the custom resource exists and targets the right workload/container:

  ```bash
  kubectl get agentobservabilitydemos -n demo-apps -o yaml
  ```

- Confirm the generated `Instrumentation` resource exists:

  ```bash
  kubectl get instrumentation -n demo-apps
  ```

- Inspect the operator reconcile logs for resource creation and workload patching:

  ```bash
  kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
  ```

- If the Deployment template changed but the Pod did not, delete the old Pod and let the Deployment recreate it:

  ```bash
  kubectl delete pod -n demo-apps <agent-pod-name>
  ```

### Coordinator not starting

- Check app logs for startup failures:

  ```bash
  kubectl logs -n demo-apps deployment/agent-no-existing --tail=200
  ```

- Confirm the runtime coordinator ConfigMap was generated and mounted:

  ```bash
  kubectl get configmap -n demo-apps
  kubectl describe pod -n demo-apps <agent-pod-name>
  ```

- Verify the custom Python auto-instrumentation image was built and loaded into kind:

  ```bash
  docker images | grep agent-observability/custom-python-autoinstrumentation
  kind get clusters
  ```

### Jaeger UI not accessible

- Confirm the port-forward is still running in the terminal where you started it:

  ```bash
  make port-forward-jaeger
  ```

- If port `16686` is already in use, choose another local port:

  ```bash
  LOCAL_PORT=26686 make port-forward-jaeger
  ```

- Verify the Jaeger Service and Pod exist:

  ```bash
  kubectl get svc,pods -n observability | grep jaeger
  ```

## Repository layout

- `operator/` - Custom operator source and unit tests.
- `runtime-coordinator/` - Python startup detection, mode selection, and activation logic.
- `custom-python-image/` - Custom Python auto-instrumentation image.
- `demo-apps/` - Demo agent and dependency services.
- `manifests/` - Kubernetes resources for CRD, operator, Collector, Jaeger, demo apps, and sample CRs.
- `scripts/` - Local workflow helpers for the end-to-end demo.
