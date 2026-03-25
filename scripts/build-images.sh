#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
IMAGE_PREFIX=${IMAGE_PREFIX:-agent-observability}
TAG=${TAG:-latest}

build_image() {
  local name=$1
  local dockerfile=$2
  echo "==> Building ${IMAGE_PREFIX}/${name}:${TAG}"
  docker build -f "${REPO_ROOT}/${dockerfile}" -t "${IMAGE_PREFIX}/${name}:${TAG}" "${REPO_ROOT}"
}

build_image operator operator/Dockerfile
build_image custom-python-autoinstrumentation custom-python-image/Dockerfile
build_image demo-agent-no-existing demo-apps/agent-no-existing/Dockerfile
build_image demo-agent-partial-existing demo-apps/agent-partial-existing/Dockerfile
build_image demo-agent-full-existing demo-apps/agent-full-existing/Dockerfile
build_image mcp-server demo-apps/mcp-server/Dockerfile

echo "Built all local PoC images successfully."
