# Scripts

These helpers make the PoC runnable end to end on a local cluster.

## Core workflow

1. `build-images.sh` builds the operator, custom Python image, and all demo app images.
2. `load-images-kind.sh` loads those images into a local kind cluster.
3. `install-deps.sh` installs cert-manager, the OpenTelemetry Operator, Jaeger, and the Collector.
4. `deploy-operator.sh` applies the CRD plus the operator Deployment and waits for rollout.
5. `deploy-demo-apps.sh` applies the demo workloads and waits for rollout.
6. `apply-sample-crs.sh` applies the three sample `AgentObservabilityDemo` resources.
7. `send-demo-traffic.sh` exercises all three demo agents.
8. `port-forward-jaeger.sh` opens the Jaeger UI locally.

## Verification shortcuts

Useful commands printed by the scripts include:

```bash
kubectl logs -n agent-observability-system deployment/agent-observability-operator
kubectl describe pod -n demo-apps <agent-pod>
kubectl logs -n observability deployment/demo-collector-collector
kubectl port-forward -n observability svc/agent-observability-jaeger 16686:16686
```
