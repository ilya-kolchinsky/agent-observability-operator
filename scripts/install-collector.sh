#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
MANIFEST_PATH=${MANIFEST_PATH:-"${REPO_ROOT}/manifests/collector/collector.yaml"}

cat <<MSG
Installing demo OpenTelemetry Collector from local manifests.
- manifest: ${MANIFEST_PATH}
- mode: single OpenTelemetryCollector custom resource managed by the OpenTelemetry Operator
MSG

kubectl apply -f "${MANIFEST_PATH}"
kubectl rollout status deployment/demo-collector-collector -n observability --timeout=180s

echo "OpenTelemetry Collector installation complete."
