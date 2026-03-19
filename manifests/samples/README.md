# Sample Manifests

This directory contains three ready-to-apply `AgentObservabilityDemo` custom resources:

- `no-existing` targets `agent-no-existing`
- `partial-existing` targets `agent-partial-existing`
- `full-existing` targets `agent-full-existing`

All three samples point at the stable in-cluster Collector service alias:

- `http://agent-observability-collector.observability.svc.cluster.local:4318`

Apply them with:

```bash
./scripts/apply-sample-crs.sh
```

After they reconcile, verify the operator and OTel Operator behavior with:

```bash
kubectl get agentobservabilitydemos -n demo-apps
kubectl logs -n agent-observability-system deployment/agent-observability-operator
kubectl get pods -n demo-apps -o wide
kubectl describe pod -n demo-apps <agent-pod-name>
```
