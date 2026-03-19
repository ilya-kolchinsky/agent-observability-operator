#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

"${SCRIPT_DIR}/send-demo-traffic.sh"

echo "Next step: run ./scripts/port-forward-jaeger.sh and open http://127.0.0.1:16686"
