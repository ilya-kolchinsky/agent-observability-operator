#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
MANIFEST_PATH=${MANIFEST_PATH:-"${REPO_ROOT}/manifests/jaeger/jaeger.yaml"}

cat <<MSG
Installing Jaeger all-in-one from local manifests.
- manifest: ${MANIFEST_PATH}
- ui service: agent-observability-jaeger.observability.svc.cluster.local:16686
MSG

kubectl apply -f "${MANIFEST_PATH}"
kubectl rollout status deployment/jaeger -n observability --timeout=180s

echo "Jaeger installation complete."
