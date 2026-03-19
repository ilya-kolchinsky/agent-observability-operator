# Demo Apps

This directory now contains realistic demo services for the observability operator PoC. Each service is container-ready, uses FastAPI, and emits clear logs so the runtime coordinator decisions can be correlated with Jaeger traces.

## Services

- `agent-no-existing/` - FastAPI + LangGraph + MCP + `httpx`, with **no** OpenTelemetry setup so the runtime coordinator should choose `FULL`.
- `agent-partial-existing/` - same workload path, but it sets partial tracing ownership signals through tracing-related environment variables so the runtime coordinator should choose `AUGMENT`.
- `agent-full-existing/` - same workload path, but explicitly configures an OpenTelemetry tracer provider, OTLP exporter, and manual FastAPI/`httpx` instrumentation so the runtime coordinator should choose `REUSE_EXISTING`.
- `mock-mcp-server/` - FastAPI-hosted MCP server using the official Python SDK with deterministic `get_weather` and `add_numbers` tools.
- `mock-external-http-service/` - simple FastAPI JSON dependency used to exercise outbound HTTP client spans.
- `common/` - shared app factory, MCP client helper, logging middleware, and tracing setup.

## Shared request flow

Each agent exposes:

- `GET /healthz`
- `POST /run`
- `POST /stream`

The `POST /run` path compiles and executes a LangGraph workflow via `graph.invoke(...)` with these steps:

1. reasoning step
2. MCP tool call to `mock-mcp-server`
3. outbound HTTP call to `mock-external-http-service`
4. response assembly

`POST /stream` runs the same compiled workflow through `graph.stream(...)` so LangGraph execution boundaries are also visible in streaming mode.

## Environment variables

The agent services share these runtime variables:

- `MCP_SERVER_URL` - defaults to `http://mock-mcp-server:8000/mcp`
- `EXTERNAL_HTTP_URL` - defaults to `http://mock-external-http-service:8000/context`
- `LOG_LEVEL` - logging level, default `INFO`

`agent-full-existing` also supports:

- `DEMO_OTLP_TRACES_ENDPOINT` - defaults to `http://localhost:4318/v1/traces`
- `DEMO_ENVIRONMENT` - resource attribute value, default `local`

## Local run examples

Run the mock dependencies first:

```bash
uvicorn main:app --app-dir demo-apps/mock-mcp-server --host 0.0.0.0 --port 8000
uvicorn main:app --app-dir demo-apps/mock-external-http-service --host 0.0.0.0 --port 8001
```

Then run any agent:

```bash
MCP_SERVER_URL=http://localhost:8000/mcp \
EXTERNAL_HTTP_URL=http://localhost:8001/context \
uvicorn main:app --app-dir demo-apps/agent-no-existing --host 0.0.0.0 --port 8010
```

Example request:

```bash
curl -X POST http://localhost:8010/run \
  -H 'content-type: application/json' \
  -d '{"prompt":"Plan a weather-aware outing","location":"Seattle","numbers":[4,5]}'
```

## Containers

Every service directory contains a Dockerfile that exposes port `8000`, installs the shared Python dependencies from `requirements.txt`, and copies the shared code from `demo-apps/common` so the apps are ready to be wired into Kubernetes manifests in a later phase.
