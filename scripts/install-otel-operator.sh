#!/usr/bin/env bash
set -euo pipefail

CERT_MANAGER_VERSION=${CERT_MANAGER_VERSION:-v1.17.1}
OTEL_OPERATOR_VERSION=${OTEL_OPERATOR_VERSION:-v0.121.0}
OTEL_OPERATOR_NAMESPACE=${OTEL_OPERATOR_NAMESPACE:-opentelemetry-operator-system}

CERT_MANAGER_MANIFEST="https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
OTEL_OPERATOR_MANIFEST="https://github.com/open-telemetry/opentelemetry-operator/releases/download/${OTEL_OPERATOR_VERSION}/opentelemetry-operator.yaml"

cat <<MSG
Installing OpenTelemetry Operator for the local demo cluster.
- install method: raw upstream manifests applied with kubectl
- cert-manager version: ${CERT_MANAGER_VERSION}
- operator version: ${OTEL_OPERATOR_VERSION}
- operator namespace: ${OTEL_OPERATOR_NAMESPACE}
MSG

kubectl apply -f "${CERT_MANAGER_MANIFEST}"
kubectl wait --namespace cert-manager --for=condition=Available deployment --all --timeout=180s

kubectl apply -f "${OTEL_OPERATOR_MANIFEST}"
kubectl wait --namespace "${OTEL_OPERATOR_NAMESPACE}" --for=condition=Available deployment --all --timeout=180s

echo "OpenTelemetry Operator installation complete."
