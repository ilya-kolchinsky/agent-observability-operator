#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

"${SCRIPT_DIR}/install-otel-operator.sh"
"${SCRIPT_DIR}/install-jaeger.sh"
"${SCRIPT_DIR}/install-collector.sh"

cat <<'MSG'
Dependency installation complete.
Demo path:
  app -> OTLP -> Collector -> Jaeger UI
MSG
