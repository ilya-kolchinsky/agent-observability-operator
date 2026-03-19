#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

"${SCRIPT_DIR}/deploy-operator.sh"
"${SCRIPT_DIR}/deploy-demo-apps.sh"
"${SCRIPT_DIR}/apply-sample-crs.sh"
