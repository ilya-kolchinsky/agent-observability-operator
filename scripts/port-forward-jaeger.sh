#!/usr/bin/env bash
set -euo pipefail

LOCAL_PORT=${LOCAL_PORT:-16686}

echo "Forwarding Jaeger UI from observability/agent-observability-jaeger to http://127.0.0.1:${LOCAL_PORT}"
kubectl port-forward -n observability svc/agent-observability-jaeger "${LOCAL_PORT}:16686"
