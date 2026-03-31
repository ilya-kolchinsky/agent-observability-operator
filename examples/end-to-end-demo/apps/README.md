# Demo Applications

This directory contains demo applications for the agent observability operator end-to-end demonstration. Each application is a containerized FastAPI service that demonstrates different instrumentation ownership scenarios.

## Applications

### Agent Services (Three Scenarios)

All three agent services share the same workload implementation (FastAPI + LangGraph + MCP + httpx) but differ in their tracing setup:

**`agent-no-existing/`**
- No OpenTelemetry setup in application code
- Platform coordinator initializes TracerProvider
- Platform instruments all available libraries
- Demonstrates: Platform owns everything

**`agent-partial-existing/`**
- Application configures TracerProvider in main.py
- Application explicitly instruments LangChain
- Platform instruments remaining libraries (httpx, requests, MCP)
- Demonstrates: Mixed ownership with auto-detection

**`agent-full-existing/`**
- Application configures TracerProvider in main.py
- Application instruments all libraries
- Platform respects application's ownership
- Demonstrates: Application owns everything

### Mock Dependencies

**`mock-mcp-server/`**
- FastAPI-hosted MCP server using official Python SDK
- Provides deterministic tools: `get_weather` and `add_numbers`
- Demonstrates MCP tool call instrumentation

**`mock-external-http-service/`**
- Simple FastAPI JSON service
- Used to exercise outbound HTTP client spans

### Shared Code

**`common/`**
- `agent_app.py` - LangGraph workflow, MCP client, HTTP calls, Ollama integration
- `logging_config.py` - Structured logging setup
- `tracing.py` - Tracing utilities and helpers

## Request Flow

Each agent exposes:
- `GET /healthz` - Health check
- `POST /run` - Execute workflow synchronously
- `POST /stream` - Execute workflow with streaming

The workflow executes these steps:
1. Reasoning step (using Ollama LLM)
2. MCP tool call to `mock-mcp-server`
3. Outbound HTTP call to `mock-external-http-service`
4. Response assembly

## Environment Variables

### Agent Services

- `MCP_SERVER_URL` - MCP server endpoint (default: `http://mock-mcp-server:8000/mcp`)
- `EXTERNAL_HTTP_URL` - External HTTP service endpoint (default: `http://mock-external-http-service:8000/context`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `OLLAMA_BASE_URL` - Ollama endpoint (default: `http://host.docker.internal:11434`)

### Full Existing Agent Only

- `DEMO_OTLP_TRACES_ENDPOINT` - OTLP traces endpoint (default: `http://localhost:4318/v1/traces`)
- `DEMO_ENVIRONMENT` - Resource attribute value (default: `local`)

## Local Development

### Run Mock Dependencies

```bash
# Terminal 1: MCP server
uvicorn main:app --app-dir examples/end-to-end-demo/apps/mock-mcp-server --host 0.0.0.0 --port 8000

# Terminal 2: External HTTP service
uvicorn main:app --app-dir examples/end-to-end-demo/apps/mock-external-http-service --host 0.0.0.0 --port 8001
```

### Run Agent

```bash
# Make sure Ollama is running locally
ollama serve

# Terminal 3: Run agent
MCP_SERVER_URL=http://localhost:8000/mcp \
EXTERNAL_HTTP_URL=http://localhost:8001/context \
uvicorn main:app --app-dir examples/end-to-end-demo/apps/agent-no-existing --host 0.0.0.0 --port 8010
```

### Test Request

```bash
curl -X POST http://localhost:8010/run \
  -H 'content-type: application/json' \
  -d '{"prompt":"Plan a weather-aware outing","location":"Seattle","numbers":[4,5]}'
```

## Docker Containers

Every service directory contains a Dockerfile that:
- Exposes port `8000`
- Installs Python dependencies from `requirements.txt`
- Copies shared code from `apps/common/`
- Sets up the service for Kubernetes deployment

Build all demo images:

```bash
make build-demo-images
```

Or build individually:

```bash
docker build -f examples/end-to-end-demo/apps/agent-no-existing/Dockerfile -t agent-observability/demo-agent-no-existing:latest .
```

## See Also

- [End-to-End Demo Guide](../README.md) - Complete demo walkthrough
- [Sample Configurations](../../sample-configurations/README.md) - Example AutoInstrumentation CRs
- [Architecture](../../../docs/ARCHITECTURE.md) - System design and component interaction
