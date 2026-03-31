#!/usr/bin/env bash
#
# Setup Ollama for demo agents
# - Check if Ollama is installed
# - Check if Ollama service is running
# - Check if phi model is available
# - Start Ollama and/or pull model as needed
#

set -euo pipefail

OLLAMA_MODEL=${OLLAMA_MODEL:-phi}
OLLAMA_HOST=${OLLAMA_HOST:-http://localhost:11434}

echo "===== Ollama Setup ====="

# Check if ollama command is available
if ! command -v ollama &> /dev/null; then
    cat >&2 <<MSG
ERROR: Ollama is not installed.

Please install Ollama:
- macOS: brew install ollama
- Linux: curl -fsSL https://ollama.com/install.sh | sh
- Or download from: https://ollama.com/download

After installation, run this script again.
MSG
    exit 1
fi

echo "✓ Ollama CLI found: $(which ollama)"

# Check if Ollama service is running
if ! curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    echo "⚠ Ollama service is not running at ${OLLAMA_HOST}"

    # Try to start Ollama in the background
    echo "→ Starting Ollama service..."

    # Check OS to determine how to start Ollama
    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS - Ollama should be started via the app or `ollama serve`
        echo "Starting Ollama server in background..."
        nohup ollama serve >/tmp/ollama.log 2>&1 &
        OLLAMA_PID=$!
        echo "  Started with PID ${OLLAMA_PID} (logs: /tmp/ollama.log)"
    else
        # Linux - similar approach
        echo "Starting Ollama server in background..."
        nohup ollama serve >/tmp/ollama.log 2>&1 &
        OLLAMA_PID=$!
        echo "  Started with PID ${OLLAMA_PID} (logs: /tmp/ollama.log)"
    fi

    # Wait for Ollama to start
    echo "→ Waiting for Ollama service to be ready..."
    for i in {1..30}; do
        if curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
            echo "✓ Ollama service is running"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "ERROR: Ollama failed to start after 30 seconds" >&2
            echo "Check logs at /tmp/ollama.log" >&2
            exit 1
        fi
        sleep 1
    done
else
    echo "✓ Ollama service is running at ${OLLAMA_HOST}"
fi

# Check if the model is available
echo "→ Checking if model '${OLLAMA_MODEL}' is available..."
if ollama list | grep -q "^${OLLAMA_MODEL}"; then
    echo "✓ Model '${OLLAMA_MODEL}' is already available"
else
    echo "⚠ Model '${OLLAMA_MODEL}' not found"
    echo "→ Pulling model '${OLLAMA_MODEL}' (this may take a few minutes)..."

    if ollama pull "${OLLAMA_MODEL}"; then
        echo "✓ Model '${OLLAMA_MODEL}' downloaded successfully"
    else
        echo "ERROR: Failed to pull model '${OLLAMA_MODEL}'" >&2
        exit 1
    fi
fi

# Verify we can query the model
echo "→ Verifying model is accessible..."
if curl -fsS "${OLLAMA_HOST}/api/show" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${OLLAMA_MODEL}\"}" >/dev/null 2>&1; then
    echo "✓ Model '${OLLAMA_MODEL}' is ready to use"
else
    echo "ERROR: Model verification failed" >&2
    exit 1
fi

cat <<MSG

===== Ollama Setup Complete =====
✓ Ollama service running at ${OLLAMA_HOST}
✓ Model '${OLLAMA_MODEL}' available
✓ Ready for demo agents

MSG
