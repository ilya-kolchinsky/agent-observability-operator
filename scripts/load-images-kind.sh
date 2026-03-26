#!/usr/bin/env bash
set -euo pipefail

KIND_CLUSTER_NAME=${KIND_CLUSTER_NAME:-kind}
IMAGE_PREFIX=${IMAGE_PREFIX:-agent-observability}
TAG=${TAG:-latest}

for image in \
  operator \
  custom-python-autoinstrumentation \
  demo-agent-no-existing \
  demo-agent-partial-existing \
  demo-agent-full-existing \
  demo-agent-auto-httpx \
  mcp-server

do
  echo "==> Loading ${IMAGE_PREFIX}/${image}:${TAG} into kind cluster ${KIND_CLUSTER_NAME}"
  kind load docker-image "${IMAGE_PREFIX}/${image}:${TAG}" --name "${KIND_CLUSTER_NAME}"
done

echo "All images loaded into kind cluster ${KIND_CLUSTER_NAME}."
