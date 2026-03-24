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

log_step "Checking runtime coordinator instrumentation decisions"
check_decision() {
  local workload=$1
  local expected_initialize_provider=$2
  local expected_instrument_fastapi=$3
  local expected_instrument_langchain=$4

  # Get diagnostics from the file
  diagnostics=$(kubectl exec -n "${DEMO_NAMESPACE}" deployment/"${workload}" -- cat /tmp/runtime-coordinator-diagnostics.log 2>/dev/null || echo "")

  if [[ -z "${diagnostics}" ]]; then
    echo "FAIL: ${workload} has no diagnostics file" >&2
    exit 1
  fi

  # Check initialize_provider decision
  if echo "${diagnostics}" | grep -qE "\"initialize_provider\":\\s*${expected_initialize_provider}"; then
    echo "PASS: ${workload} initialize_provider=${expected_initialize_provider}"
  else
    echo "FAIL: ${workload} initialize_provider should be ${expected_initialize_provider}" >&2
    echo "Diagnostics:" >&2
    echo "${diagnostics}" >&2
    exit 1
  fi

  # Check instrument_fastapi decision
  if echo "${diagnostics}" | grep -qE "\"instrument_fastapi\":\\s*${expected_instrument_fastapi}"; then
    echo "PASS: ${workload} instrument_fastapi=${expected_instrument_fastapi}"
  else
    echo "FAIL: ${workload} instrument_fastapi should be ${expected_instrument_fastapi}" >&2
    echo "Diagnostics:" >&2
    echo "${diagnostics}" >&2
    exit 1
  fi

  # Check instrument_langchain decision (as representative of agent-level instrumentation)
  if echo "${diagnostics}" | grep -qE "\"instrument_langchain\":\\s*${expected_instrument_langchain}"; then
    echo "PASS: ${workload} instrument_langchain=${expected_instrument_langchain}"
  else
    echo "FAIL: ${workload} instrument_langchain should be ${expected_instrument_langchain}" >&2
    echo "Diagnostics:" >&2
    echo "${diagnostics}" >&2
    exit 1
  fi
}

# Expected decisions with new fine-grained approach:
#
# IMPORTANT: The coordinator runs at sitecustomize.py time, BEFORE the application's main.py runs.
# This means:
# - agent-no-existing: No app-level setup → coordinator initializes everything
# - agent-partial-existing: App code in main.py sets up provider + HTTP, but runs AFTER coordinator → coordinator makes same decisions as no-existing
# - agent-full-existing: App code in main.py sets up everything, but runs AFTER coordinator → coordinator makes same decisions as no-existing
#
# The coordinator detects:
# - initialize_provider=true (ProxyTracerProvider at sitecustomize time)
# - instrument_fastapi=false (already instrumented by OTel operator's auto-instrumentation)
# - instrument_langchain=false (not installed in demo apps)
# - instrument_langgraph=true (available but not yet instrumented)
# - instrument_mcp=true (available but not yet instrumented)
#
# All three agents should have the same coordinator decisions since they all look identical at sitecustomize time.
check_decision agent-no-existing true false false
check_decision agent-partial-existing true false false
check_decision agent-full-existing true false false

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
