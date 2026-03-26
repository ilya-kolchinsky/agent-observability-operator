#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

kubectl apply -f "${REPO_ROOT}/manifests/demo/demo-apps.yaml"
for deployment in mcp-server agent-no-existing agent-partial-existing agent-full-existing agent-auto-httpx; do
  kubectl rollout status deployment/"${deployment}" -n demo-apps --timeout=180s
done

cat <<'MSG'
Demo apps deployed.

Stable service names:
- mcp-server.demo-apps.svc.cluster.local
- agent-no-existing.demo-apps.svc.cluster.local
- agent-partial-existing.demo-apps.svc.cluster.local
- agent-full-existing.demo-apps.svc.cluster.local
- agent-auto-httpx.demo-apps.svc.cluster.local

NOTE: Ollama runs locally on your host machine.
Make sure it's running with: ollama serve
Pull the phi model with: ollama pull phi
MSG
