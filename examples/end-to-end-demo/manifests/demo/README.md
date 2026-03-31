# Demo Workload Manifests

This directory deploys the demo applications for the end-to-end demonstration.

## Workloads

**Agent Services (Three Scenarios):**
- `agent-no-existing` - Platform owns all instrumentation
- `agent-partial-existing` - Mixed ownership (auto-detection enabled)
- `agent-full-existing` - Application owns all instrumentation

**Mock Dependencies:**
- `mock-mcp-server` - MCP server for tool calls
- `mock-external-http-service` - External HTTP service

Each Deployment has a matching Service in the `demo-apps` namespace. The three agent Deployments use a container named `app` for consistent targeting by the operator.

## Install

```bash
examples/end-to-end-demo/scripts/deploy-demo-apps.sh
```

Or via Makefile:

```bash
make deploy-demo-apps
```

## Verify

Check that all workloads are running:

```bash
kubectl get deployments -n demo-apps
kubectl get pods -n demo-apps
```

Expected deployments:
- agent-no-existing
- agent-partial-existing
- agent-full-existing
- mock-mcp-server
- mock-external-http-service

## Service Endpoints

Inside the cluster:
- `agent-no-existing.demo-apps.svc.cluster.local:8000`
- `agent-partial-existing.demo-apps.svc.cluster.local:8000`
- `agent-full-existing.demo-apps.svc.cluster.local:8000`
- `mock-mcp-server.demo-apps.svc.cluster.local:8000`
- `mock-external-http-service.demo-apps.svc.cluster.local:8000`

## See Also

- [Demo Applications](../../apps/README.md) - Application implementation details
- [Sample Configurations](../../../sample-configurations/README.md) - AutoInstrumentation CR examples
