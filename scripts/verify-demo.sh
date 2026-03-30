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
for demo in no-existing partial-existing full-existing auto-httpx; do
  require_resource "AgentObservabilityDemo/${demo} exists" kubectl get agentobservabilitydemo "${demo}" -n "${DEMO_NAMESPACE}"
  require_resource "Instrumentation/${demo}-instrumentation exists" kubectl get instrumentation "${demo}-instrumentation" -n "${DEMO_NAMESPACE}"
done

log_step "Checking operator reconciliation logs"
require_grep \
  "operator reported Instrumentation creation or refresh" \
  'created Instrumentation resource|updated Instrumentation resource|Instrumentation resource already up to date' \
  kubectl logs -n "${OPERATOR_NAMESPACE}" deployment/agent-observability-operator --tail=400

log_step "Checking mutated workload pods"
for workload in agent-no-existing agent-partial-existing agent-full-existing agent-auto-httpx; do
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

log_step "Checking runtime coordinator config-driven decisions"
check_config_decision() {
  local workload=$1
  local expected_initialize_provider=$2
  local expected_instrument_fastapi=$3
  local expected_instrument_httpx=$4
  local expected_instrument_requests=$5
  local expected_instrument_langchain=$6
  local expected_instrument_mcp=$7

  # Get diagnostics from the file
  diagnostics=$(kubectl exec -n "${DEMO_NAMESPACE}" deployment/"${workload}" -- cat /tmp/runtime-coordinator-diagnostics.log 2>/dev/null || echo "")

  if [[ -z "${diagnostics}" ]]; then
    echo "FAIL: ${workload} has no diagnostics file" >&2
    exit 1
  fi

  # Helper function to check a specific decision
  check_decision_value() {
    local decision_name=$1
    local expected_value=$2

    if echo "${diagnostics}" | grep -qE "\"${decision_name}\":\\s*${expected_value}"; then
      echo "PASS: ${workload} ${decision_name}=${expected_value}"
    else
      echo "FAIL: ${workload} ${decision_name} should be ${expected_value}" >&2
      echo "Diagnostics:" >&2
      echo "${diagnostics}" >&2
      exit 1
    fi
  }

  # Check all decisions
  check_decision_value "initialize_provider" "${expected_initialize_provider}"
  check_decision_value "instrument_fastapi" "${expected_instrument_fastapi}"
  check_decision_value "instrument_httpx" "${expected_instrument_httpx}"
  check_decision_value "instrument_requests" "${expected_instrument_requests}"
  check_decision_value "instrument_langchain" "${expected_instrument_langchain}"
  check_decision_value "instrument_mcp" "${expected_instrument_mcp}"
}

# Expected config-driven decisions (based on sample CRs):
#
# Simplified baseline: pure config-driven instrumentation (no auto-detection).
#
# agent-no-existing (platform owns EVERYTHING):
#   tracerProvider: platform → initialize_provider=true
#   All instrumentation flags: true
#
# agent-partial-existing (MIXED ownership):
#   tracerProvider: app → initialize_provider=false (app initializes in main.py)
#   fastapi: false (app handles)
#   httpx: true, requests: true
#   langchain: false (app handles)
#   mcp: true (platform handles - app doesn't instrument it)
#
# agent-full-existing (app owns EVERYTHING):
#   tracerProvider: app → initialize_provider=false
#   All instrumentation flags: false (app handles everything)

# Format: workload initialize_provider fastapi httpx requests langchain mcp
check_config_decision agent-no-existing true true true true true true
check_config_decision agent-partial-existing false false true true false true
check_config_decision agent-full-existing false false false false false false
# agent-auto-httpx: Both httpx and requests are "auto" (deferred to runtime wrappers)
# Bootstrap decisions show false for both (instrumentation deferred)
check_config_decision agent-auto-httpx false false false false false true

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
