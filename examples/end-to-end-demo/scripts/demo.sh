#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEMO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd -- "${DEMO_ROOT}/../.." && pwd)

step() {
  printf '\n===== %s =====\n' "$1"
}

step '1. Start local kind cluster'
"${SCRIPT_DIR}/create-kind-cluster.sh"

step '2. Install OpenTelemetry Operator, Collector, and Jaeger'
"${SCRIPT_DIR}/install-deps.sh"

step '3. Build core images'
"${REPO_ROOT}/core/scripts/build-core-images.sh"

step '4. Build demo images'
"${SCRIPT_DIR}/build-demo-images.sh"

step '5. Load images into kind'
"${SCRIPT_DIR}/load-images-kind.sh"

step '6. Deploy the custom operator'
"${REPO_ROOT}/core/scripts/deploy-operator.sh"

step '7. Setup Ollama (LLM for demo agents)'
"${SCRIPT_DIR}/setup-ollama.sh"

step '8. Deploy demo app variants'
"${SCRIPT_DIR}/deploy-demo-apps.sh"

step '9. Apply the custom AutoInstrumentation resources'
"${SCRIPT_DIR}/apply-sample-crs.sh"

step '10. Wait for operator to reconcile and pods to be instrumented'
printf 'Waiting for Instrumentation resources and instrumented pods...\n'

# First, wait for Instrumentation resources to be created
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

# Then wait for running pods to actually have the instrumentation annotation
# (This implicitly confirms Deployments were patched and rollout completed)
for workload in agent-no-existing agent-partial-existing agent-full-existing; do
  timeout=60
  while true; do
    pod=$(kubectl get pods -n demo-apps -l "app.kubernetes.io/name=${workload}" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [[ -z "${pod}" ]]; then
      if [ $timeout -le 0 ]; then
        echo "ERROR: Timeout waiting for running pod for ${workload}"
        exit 1
      fi
      sleep 1
      timeout=$((timeout - 1))
      continue
    fi

    annotation=$(kubectl get pod "${pod}" -n demo-apps -o jsonpath='{.metadata.annotations.instrumentation\.opentelemetry\.io/inject-python}' 2>/dev/null || echo "")
    if [[ -n "${annotation}" ]]; then
      echo "✓ Pod ${pod} has inject-python annotation: ${annotation}"
      break
    fi

    if [ $timeout -le 0 ]; then
      echo "ERROR: Timeout waiting for pod ${pod} to have inject-python annotation"
      exit 1
    fi
    sleep 1
    timeout=$((timeout - 1))
  done
done

step '11. Verify generated resources and pod mutation before sending traffic'
"${SCRIPT_DIR}/verify-demo.sh"

step '12. Send traffic to the demo agent endpoints'
"${SCRIPT_DIR}/send-demo-traffic.sh"

cat <<'MSG'

===== 13-14. Open Jaeger and inspect traces =====
Run examples/end-to-end-demo/scripts/port-forward-jaeger.sh in a separate terminal and open http://127.0.0.1:16686.
Then search for services:
- agent-no-existing
- agent-partial-existing
- agent-full-existing

You should now be able to verify the full PoC with your own eyes.
MSG
