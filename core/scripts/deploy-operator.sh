#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CORE_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

kubectl apply -f "${CORE_ROOT}/deploy/crd/autoinstrumentation-crd.yaml"
kubectl apply -f "${CORE_ROOT}/deploy/operator/operator.yaml"
kubectl rollout status deployment/agent-observability-operator -n agent-observability-system --timeout=180s

cat <<'MSG'
Operator deployed.

Verification hints:
- operator reconcile logs:
    kubectl logs -n agent-observability-system deployment/agent-observability-operator
- custom resources:
    kubectl get agentobservabilitydemos -A
MSG
