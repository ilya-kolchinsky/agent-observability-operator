#!/usr/bin/env bash
set -euo pipefail

DEMO_NAMESPACE=${DEMO_NAMESPACE:-demo-apps}
OBS_NAMESPACE=${OBS_NAMESPACE:-observability}
OPERATOR_NAMESPACE=${OPERATOR_NAMESPACE:-agent-observability-system}

log_step() {
  printf '\n==> %s\n' "$1"
}

require_resource() {
  local description=$1
  shift

  if "$@" >/dev/null; then
    echo "PASS: ${description}"
  else
    echo "FAIL: ${description}" >&2
    exit 1
  fi
}

require_grep() {
  local description=$1
  local pattern=$2
  shift 2

  if "$@" | grep -E "${pattern}"; then
    echo "PASS: ${description}"
  else
    echo "FAIL: ${description}" >&2
    exit 1
  fi
}

log_step "Checking custom resources and generated Instrumentation resources"
for demo in no-existing partial-existing full-existing; do
  require_resource "AgentObservabilityDemo/${demo} exists" kubectl get agentobservabilitydemo "${demo}" -n "${DEMO_NAMESPACE}"
  require_resource "Instrumentation/${demo}-instrumentation exists" kubectl get instrumentation "${demo}-instrumentation" -n "${DEMO_NAMESPACE}"
done

log_step "Checking operator reconciliation logs"
require_grep \
  "operator reported Instrumentation creation or refresh" \
  'created Instrumentation resource|updated Instrumentation resource|Instrumentation resource already up to date' \
  kubectl logs -n "${OPERATOR_NAMESPACE}" deployment/agent-observability-operator --tail=400

log_step "Checking mutated workload pods"
for workload in agent-no-existing agent-partial-existing agent-full-existing; do
  pod=$(kubectl get pods -n "${DEMO_NAMESPACE}" -l "app.kubernetes.io/name=${workload}" -o jsonpath='{.items[0].metadata.name}')
  if [[ -z "${pod}" ]]; then
    echo "FAIL: could not find Pod for ${workload}" >&2
    exit 1
  fi

  annotation=$(kubectl get pod "${pod}" -n "${DEMO_NAMESPACE}" -o jsonpath='{.metadata.annotations.instrumentation\.opentelemetry\.io/inject-python}')
  if [[ -z "${annotation}" ]]; then
    echo "FAIL: ${pod} is missing instrumentation.opentelemetry.io/inject-python" >&2
    exit 1
  fi
  echo "PASS: ${pod} has inject-python=${annotation}"

  require_grep \
    "${pod} includes OpenTelemetry-related env or injected init container" \
    'OTEL_EXPORTER_OTLP_ENDPOINT|OTEL_EXPORTER_OTLP_TRACES_ENDPOINT|opentelemetry-auto-instrumentation|opentelemetry-instrumentation' \
    kubectl describe pod "${pod}" -n "${DEMO_NAMESPACE}"
done

log_step "Checking runtime coordinator mode selection logs"
check_mode() {
  local workload=$1
  local expected_mode=$2

  require_grep \
    "${workload} selected ${expected_mode}" \
    "selected_mode.*${expected_mode}|${expected_mode}.*selected_mode|\"${expected_mode}\"" \
    kubectl logs -n "${DEMO_NAMESPACE}" deployment/"${workload}" --tail=200
}

check_mode agent-no-existing FULL
check_mode agent-partial-existing AUGMENT
check_mode agent-full-existing REUSE_EXISTING

log_step "Checking collector and Jaeger are reachable inside the cluster"
require_resource "Collector deployment is available" kubectl get deployment demo-collector-collector -n "${OBS_NAMESPACE}"
require_resource "Jaeger deployment is available" kubectl get deployment jaeger -n "${OBS_NAMESPACE}"

cat <<MSG

Verification checks passed.

Recommended next commands:
- Send traffic:
    make send-demo-traffic
- Inspect Collector logs for exported traces:
    kubectl logs -n ${OBS_NAMESPACE} deployment/demo-collector-collector --tail=200
- Open Jaeger locally:
    make port-forward-jaeger
MSG
