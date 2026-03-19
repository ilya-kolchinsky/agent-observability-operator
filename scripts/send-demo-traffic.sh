#!/usr/bin/env bash
set -euo pipefail

RUNNER_IMAGE=${RUNNER_IMAGE:-curlimages/curl:8.7.1}
RUNNER_NAME="demo-traffic-$(date +%s)"

kubectl run "${RUNNER_NAME}" \
  --rm -i --restart=Never \
  --namespace demo-apps \
  --image "${RUNNER_IMAGE}" \
  --command -- sh -ceu '
services="agent-no-existing agent-partial-existing agent-full-existing"
for service in ${services}; do
  echo "==> Sending demo traffic to ${service}"
  curl -fsS "http://${service}.demo-apps.svc.cluster.local:8000/healthz"
  echo
  curl -fsS -X POST "http://${service}.demo-apps.svc.cluster.local:8000/run" \
    -H "content-type: application/json" \
    -d "{\"prompt\":\"Plan a weather-aware outing\",\"location\":\"Seattle\",\"numbers\":[4,5]}"
  echo
  curl -fsS -X POST "http://${service}.demo-apps.svc.cluster.local:8000/stream" \
    -H "content-type: application/json" \
    -d "{\"prompt\":\"Stream a weather-aware outing\",\"location\":\"Austin\",\"numbers\":[7,8]}"
  echo
  echo
 done
'

cat <<'MSG'
Demo traffic finished.

Verification hints:
- runtime coordinator mode selection:
    kubectl logs -n demo-apps deployment/agent-no-existing --tail=100
    kubectl logs -n demo-apps deployment/agent-partial-existing --tail=100
    kubectl logs -n demo-apps deployment/agent-full-existing --tail=100
- Collector received OTLP and exported to Jaeger:
    kubectl logs -n observability deployment/demo-collector-collector --tail=200
- Jaeger should now show traces after port-forwarding:
    ./scripts/port-forward-jaeger.sh
MSG
