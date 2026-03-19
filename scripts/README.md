# Scripts

These helpers make the PoC runnable end to end on a local cluster.

## Core workflow

1. `create-kind-cluster.sh` creates or reuses a local kind cluster and switches kubectl to it.
2. `build-images.sh` builds the operator, custom Python image, and all demo app images.
3. `load-images-kind.sh` loads those images into a local kind cluster.
4. `install-deps.sh` installs cert-manager, the OpenTelemetry Operator, the Collector, and Jaeger.
5. `deploy-operator.sh` applies the CRD plus the operator Deployment and waits for rollout.
6. `deploy-demo-apps.sh` applies the demo workloads and waits for rollout.
7. `apply-sample-crs.sh` applies the three sample `AgentObservabilityDemo` resources.
8. `verify-demo.sh` checks generated `Instrumentation`, mutated Pods, and runtime coordinator mode selection.
9. `send-demo-traffic.sh` exercises all three demo agents.
10. `port-forward-jaeger.sh` opens the Jaeger UI locally.
11. `demo.sh` runs the full walkthrough up to the point where you open Jaeger in the browser.

## Suggested Make targets

```bash
make create-kind-cluster
make install-deps
make build-images
make load-images-kind
make deploy-operator
make deploy-demo-apps
make apply-sample-crs
make verify-demo
make send-demo-traffic
make port-forward-jaeger
make demo-walkthrough
```

## Verification shortcuts

Useful commands printed by the scripts include:

```bash
kubectl logs -n agent-observability-system deployment/agent-observability-operator
kubectl describe pod -n demo-apps <agent-pod>
kubectl logs -n observability deployment/demo-collector-collector
kubectl port-forward -n observability svc/agent-observability-jaeger 16686:16686
```
