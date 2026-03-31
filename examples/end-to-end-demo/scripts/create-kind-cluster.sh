#!/usr/bin/env bash
set -euo pipefail

KIND_CLUSTER_NAME=${KIND_CLUSTER_NAME:-kind}
KUBECONFIG_CONTEXT=${KUBECONFIG_CONTEXT:-kind-${KIND_CLUSTER_NAME}}

if ! command -v kind >/dev/null 2>&1; then
  echo "kind is required but was not found in PATH." >&2
  exit 1
fi

if kind get clusters | grep -Fxq "${KIND_CLUSTER_NAME}"; then
  echo "kind cluster ${KIND_CLUSTER_NAME} already exists."
else
  echo "Creating kind cluster ${KIND_CLUSTER_NAME}."
  kind create cluster --name "${KIND_CLUSTER_NAME}"
fi

kubectl cluster-info --context "${KUBECONFIG_CONTEXT}" >/dev/null
kubectl config use-context "${KUBECONFIG_CONTEXT}" >/dev/null

cat <<MSG
kind cluster is ready.

Verification hints:
- current context:
    kubectl config current-context
- nodes:
    kubectl get nodes
MSG
