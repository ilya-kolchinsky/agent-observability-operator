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
