#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CORE_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd -- "${CORE_ROOT}/.." && pwd)
IMAGE_PREFIX=${IMAGE_PREFIX:-agent-observability}
TAG=${TAG:-latest}

# Generate requirements.txt from plugin dependencies
echo "==> Generating requirements.txt from plugin dependencies"
python "${SCRIPT_DIR}/generate-requirements.py"

build_image() {
  local name=$1
  local dockerfile=$2
  echo "==> Building ${IMAGE_PREFIX}/${name}:${TAG}"
  docker build -f "${REPO_ROOT}/${dockerfile}" -t "${IMAGE_PREFIX}/${name}:${TAG}" "${REPO_ROOT}"
}

build_image operator core/operator/Dockerfile
build_image custom-python-autoinstrumentation core/custom-python-image/Dockerfile

echo "Built core images successfully."
