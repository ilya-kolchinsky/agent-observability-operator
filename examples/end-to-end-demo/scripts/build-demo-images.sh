#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEMO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd -- "${DEMO_ROOT}/../.." && pwd)
IMAGE_PREFIX=${IMAGE_PREFIX:-agent-observability}
TAG=${TAG:-latest}

build_image() {
  local name=$1
  local dockerfile=$2
  echo "==> Building ${IMAGE_PREFIX}/${name}:${TAG}"
  docker build -f "${REPO_ROOT}/${dockerfile}" -t "${IMAGE_PREFIX}/${name}:${TAG}" "${REPO_ROOT}"
}

# Build demo images
build_image demo-agent-no-existing examples/end-to-end-demo/apps/agent-no-existing/Dockerfile
build_image demo-agent-partial-existing examples/end-to-end-demo/apps/agent-partial-existing/Dockerfile
build_image demo-agent-full-existing examples/end-to-end-demo/apps/agent-full-existing/Dockerfile
build_image mcp-server examples/end-to-end-demo/apps/mcp-server/Dockerfile

echo "Built demo images successfully."
