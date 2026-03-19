# Demo Manifests

This directory deploys the full set of demo workloads used by the PoC:

- `mock-mcp-server`
- `mock-external-http-service`
- `agent-no-existing`
- `agent-partial-existing`
- `agent-full-existing`

Each Deployment has a matching stable Service in the `demo-apps` namespace. The three agent Deployments intentionally use a container named `app` so the custom operator can target them consistently when it adds OpenTelemetry injection annotations, Collector env vars, and the runtime coordinator ConfigMap mount.

Install with:

```bash
./scripts/deploy-demo-apps.sh
```
