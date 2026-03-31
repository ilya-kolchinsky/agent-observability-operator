#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
OPERATOR_DIR="${REPO_ROOT}/operator"
BINARY_PATH="${REPO_ROOT}/bin/agent-observability-operator"
IMAGE_TAG=${IMAGE_TAG:-agent-observability/operator:local-check}
RUN_DURATION_SECONDS=${RUN_DURATION_SECONDS:-5}
METRICS_ADDR=${METRICS_ADDR:-127.0.0.1:18080}
PROBE_ADDR=${PROBE_ADDR:-127.0.0.1:18081}

mkdir -p "${REPO_ROOT}/bin"

echo "==> Building operator packages with real upstream modules"
(
  cd "${OPERATOR_DIR}"
  go build ./...
  go build -o "${BINARY_PATH}" ./main.go
)

echo "==> Building operator image"
docker build -f "${REPO_ROOT}/operator/Dockerfile" -t "${IMAGE_TAG}" "${REPO_ROOT}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "WARNING: kubectl is not installed; skipping runtime manager sanity check."
  exit 0
fi

if ! kubectl version --request-timeout=5s >/dev/null 2>&1; then
  echo "WARNING: no reachable Kubernetes cluster detected; skipping runtime manager sanity check."
  exit 0
fi

echo "==> Starting operator binary against the current Kubernetes context"
"${BINARY_PATH}" \
  --metrics-bind-address="${METRICS_ADDR}" \
  --health-probe-bind-address="${PROBE_ADDR}" \
  >"${REPO_ROOT}/bin/operator-local-check.log" 2>&1 &
operator_pid=$!

cleanup() {
  if kill -0 "${operator_pid}" >/dev/null 2>&1; then
    kill "${operator_pid}" >/dev/null 2>&1 || true
    wait "${operator_pid}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

sleep "${RUN_DURATION_SECONDS}"
if ! kill -0 "${operator_pid}" >/dev/null 2>&1; then
  echo "ERROR: operator process exited before the sanity check window elapsed."
  echo "--- operator log ---"
  cat "${REPO_ROOT}/bin/operator-local-check.log"
  exit 1
fi

echo "Operator manager remained running for ${RUN_DURATION_SECONDS}s."
