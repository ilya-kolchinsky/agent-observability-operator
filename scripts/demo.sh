#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

step() {
  printf '\n===== %s =====\n' "$1"
}

step '1. Start local kind cluster'
"${SCRIPT_DIR}/create-kind-cluster.sh"

step '2. Install OpenTelemetry Operator, Collector, and Jaeger'
"${SCRIPT_DIR}/install-deps.sh"

step '3. Build local images'
"${SCRIPT_DIR}/build-images.sh"

step '4. Load images into kind'
"${SCRIPT_DIR}/load-images-kind.sh"

step '5. Deploy the custom operator'
"${SCRIPT_DIR}/deploy-operator.sh"

step '6. Deploy demo app variants'
"${SCRIPT_DIR}/deploy-demo-apps.sh"

step '7. Apply the custom AgentObservabilityDemo resources'
"${SCRIPT_DIR}/apply-sample-crs.sh"

step '7b. Wait for operator to reconcile and create Instrumentation resources'
printf 'Waiting for Instrumentation resources to be created...\n'
for demo in no-existing partial-existing full-existing; do
  timeout=30
  while ! kubectl get instrumentation "${demo}-instrumentation" -n demo-apps >/dev/null 2>&1; do
    if [ $timeout -le 0 ]; then
      echo "ERROR: Timeout waiting for Instrumentation/${demo}-instrumentation"
      exit 1
    fi
    sleep 1
    timeout=$((timeout - 1))
  done
  echo "✓ Instrumentation/${demo}-instrumentation created"
done

step '8. Verify generated resources and pod mutation before sending traffic'
"${SCRIPT_DIR}/verify-demo.sh"

step '9. Send traffic to the demo agent endpoints'
"${SCRIPT_DIR}/send-demo-traffic.sh"

cat <<'MSG'

===== 10-11. Open Jaeger and inspect traces =====
Run ./scripts/port-forward-jaeger.sh in a separate terminal and open http://127.0.0.1:16686.
Then search for services:
- agent-no-existing
- agent-partial-existing
- agent-full-existing

You should now be able to verify the full PoC with your own eyes.
MSG
