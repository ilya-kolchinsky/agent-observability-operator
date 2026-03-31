# Runtime Coordinator

The runtime coordinator is the Python-side policy engine embedded in the custom auto-instrumentation image. Its job is to make startup-time observability decisions safely.

The key design principle is:

> the image contains instrumentation packages, but the coordinator decides which instrumentors are actually activated

That separation lets the platform ship a capable image without assuming every app should be instrumented the same way or that all preinstalled packages should be turned on.

## What the runtime coordinator does

At import/startup time the coordinator performs a small pipeline:

1. **Load config** from `AGENT_OBS_*` environment variables and an optional config file.
2. **Detect runtime state** using heuristics focused on user/application-owned tracing, not on the mere presence of packages in the image.
3. **Make fine-grained instrumentation decisions** for each supported framework and component.
4. **Apply the decisions** with defensive error handling so startup never crashes the application.
5. **Emit structured diagnostics** including detected signals, individual decisions, and actions taken.

The implementation is intentionally conservative and PoC-oriented: if a package or instrumentor is unavailable, the coordinator logs a skip instead of failing the app.

## Current runtime flow

The main entrypoint is `agent_obs_runtime.bootstrap`.

### 1. Configuration

The coordinator currently loads configuration via environment variables and mounted config files from the operator:

- Service name, namespace, and deployment metadata
- Collector endpoints for OTLP export
- Optional feature flags and overrides

If loading fails, the coordinator falls back to defaults and records a warning.

### 2. Detection

Detection is intentionally focused on **tracing ownership** signals such as:

- a non-default tracer provider
- active span processors/exporters
- tracing-related environment variables
- known tracing packages or indicators
- framework presence signals for FastAPI, ASGI/Starlette, `httpx`, `requests`, MCP, LangChain, and LangGraph
- lightweight framework instrumentation hints used to avoid duplicate activation

This distinction matters: the custom image may contain OpenTelemetry and instrumentor packages, but that does **not** mean the user app has already chosen or activated instrumentation.

### 3. Fine-grained decision making

The coordinator makes independent decisions for each instrumentation target:

- **`should_initialize_provider()`** - Initialize a TracerProvider if only ProxyTracerProvider is present
- **`should_instrument_fastapi()`** - Instrument FastAPI if available and not already instrumented
- **`should_instrument_httpx()`** - Instrument httpx if available and not already instrumented
- **`should_instrument_requests()`** - Instrument requests if available and not already instrumented
- **`should_instrument_langchain()`** - Instrument LangChain if available and not already instrumented
- **`should_instrument_langgraph()`** - Instrument LangGraph if available and not already instrumented
- **`should_instrument_mcp()`** - Instrument MCP boundaries if available and not already instrumented

Decision rules are simple and defensive:

- Don't instrument what's already instrumented
- Don't instrument what isn't available
- Do initialize a provider if the app hasn't configured one yet

### 4. Actuation

`agent_obs_runtime.instrumentation` applies each decision safely.

#### Provider initialization

If `should_initialize_provider()` returns true, the coordinator:

- Installs a default OpenTelemetry SDK tracer provider
- Attaches a span processor/exporter configured to send traces to the collector
- Never overrides an existing configured provider

#### Supported runtime targets

- **FastAPI / ASGI**: prefer `FastAPIInstrumentor`, fall back to `ASGIInstrumentor` when available
- **HTTP egress**: activate `HTTPXClientInstrumentor` and/or `RequestsInstrumentor` conditionally
- **MCP**: apply a lightweight wrapper to a representative tool invocation path
- **LangChain**: prefer the official OpenTelemetry LangChain instrumentor if installed
- **LangGraph**: patch top-level compiled graph execution methods such as `invoke`, `stream`, and `astream`

All activations are wrapped in defensive error handling. The coordinator logs whether each target was enabled, skipped, or failed, along with a reason.

## Diagnostics output

Startup diagnostics are emitted as structured JSON to stderr and a diagnostics log file.

The current report includes:

- loaded configuration
- detected tracing and framework signals (provider state, framework availability, instrumentation state)
- individual instrumentation decisions for each framework
- warnings encountered during detection or actuation

This makes it easy to understand which instrumentations were activated and why.

## Supported instrumentation in this PoC

The current implementation is deliberately narrow and only targets:

- FastAPI / ASGI ingress
- `httpx` and `requests` egress
- MCP client tool-boundary wrapping
- LangChain via official OTel instrumentor when present
- LangGraph via lightweight execution-boundary monkeypatching

This is enough to demonstrate runtime control without trying to support every Python framework.

## Safety properties

The coordinator is designed around startup safety:

- it treats missing optional packages as normal
- it avoids overriding an app-owned provider
- it never instruments what's already instrumented
- it favors skip-with-logging over hard failure
- it keeps monkeypatching shallow and narrowly targeted
- it emits diagnostics even when parts of the startup pipeline fail

## Extension points beyond this PoC

This PoC is intentionally small, but the coordinator can be extended in several useful directions.

### Additional detection heuristics

Examples:

- detect user-created resource attributes or service naming conventions
- detect explicit exporter initialization patterns
- detect app-specific framework wrappers or middleware registration
- detect richer LangGraph or agent-framework ownership signals

### More plan dimensions

Examples:

- per-target enable/disable config instead of simple patcher allowlists
- ingress/egress sampling policies
- provider/exporter initialization strategies
- richer suppression rules for specific workloads or environments

### More runtime targets

Examples:

- database client instrumentation
- queue/stream instrumentation
- model-provider SDK instrumentation
- deeper agent framework hooks once stable APIs are identified

### Better platform integration

Examples:

- export startup diagnostics as structured events or metrics
- feed operator-side policy into the runtime plan via mounted config
- add richer compatibility checks per image build
- surface runtime coordinator decisions in Kubernetes status or CR conditions

## Repository structure

Relevant files:

- `agent_obs_runtime/bootstrap.py` - startup orchestration and diagnostics
- `agent_obs_runtime/detection.py` - tracing ownership and framework detection, plus decision functions
- `agent_obs_runtime/instrumentation.py` - instrumentation actuation for all supported frameworks

## Limitations

This remains a PoC. Notable limitations include:

- no broad framework coverage beyond the small supported set
- heuristic duplicate detection rather than deep semantic certainty
- best-effort provider initialization rather than a production-ready SDK bootstrap story
- minimal monkeypatch-based integrations for MCP and LangGraph
- timing issue: the coordinator runs at sitecustomize time, before the application's main.py, so it cannot detect what the application will set up later

Those tradeoffs are intentional for this phase: the goal is to demonstrate controlled runtime activation, not a complete production observability platform.
