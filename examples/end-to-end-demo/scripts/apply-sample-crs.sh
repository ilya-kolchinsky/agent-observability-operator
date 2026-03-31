#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEMO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd -- "${DEMO_ROOT}/../.." && pwd)

kubectl apply -f "${REPO_ROOT}/examples/sample-configurations/autoinstrumentation-sample.yaml"

cat <<'MSG'
Sample CRs applied.

Verification hints:
- operator reconciled the CRs:
    kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
- generated Instrumentation + ConfigMaps:
    kubectl get instrumentation,configmap -n demo-apps
- OTel Operator injected instrumentation into Pods:
    kubectl get pods -n demo-apps
    kubectl describe pod -n demo-apps <agent-pod>
MSG
