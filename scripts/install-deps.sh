#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

"${SCRIPT_DIR}/install-otel-operator.sh"
"${SCRIPT_DIR}/install-collector.sh"
"${SCRIPT_DIR}/install-jaeger.sh"

cat <<'MSG'
Dependency installation complete.

Stable service names:
- Collector OTLP endpoint: http://agent-observability-collector.observability.svc.cluster.local:4318
- Jaeger UI service: agent-observability-jaeger.observability.svc.cluster.local:16686
- Jaeger OTLP ingest: jaeger-collector.observability.svc.cluster.local:4317

Telemetry path:
  app -> OTLP -> Collector -> Jaeger UI
MSG
