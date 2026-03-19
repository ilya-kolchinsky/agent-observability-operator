# Runtime Coordinator

The runtime coordinator is the Python-side policy engine embedded in the custom auto-instrumentation image. Its job is to make startup-time observability decisions safely.

The key design principle is:

> the image contains instrumentation packages, but the coordinator decides which instrumentors are actually activated

That separation lets the platform ship a capable image without assuming every app should be instrumented the same way or that all preinstalled packages should be turned on.

## What the runtime coordinator does

At import/startup time the coordinator performs a small pipeline:

1. **Load config** from `AGENT_OBS_*` environment variables and an optional config file.
2. **Detect runtime state** using heuristics focused on user/application-owned tracing, not on the mere presence of packages in the image.
3. **Select a coordination mode** using the existing runtime mode chooser.
4. **Build an instrumentation plan** describing what to activate.
5. **Apply the plan** with defensive error handling so startup never crashes the application.
6. **Emit structured diagnostics** including detected signals, selected mode, plan contents, and actions taken.

The implementation is intentionally conservative and PoC-oriented: if a package or instrumentor is unavailable, the coordinator logs a skip instead of failing the app.

## Current runtime flow

The main entrypoint is `agent_obs_runtime.bootstrap`.

### 1. Configuration

The coordinator currently loads the following settings via `AGENT_OBS_*` environment variables or an optional config file:

- `AGENT_OBS_MODE` - explicit mode override (`FULL`, `AUGMENT`, `REUSE_EXISTING`, `OFF`)
- `AGENT_OBS_DIAGNOSTICS_LEVEL` - diagnostics verbosity selector
- `AGENT_OBS_ENABLED_HEURISTICS` - comma-separated list of enabled detection heuristics
- `AGENT_OBS_ENABLED_PATCHERS` - comma-separated list of instrumentation targets to allow
- `AGENT_OBS_SUPPRESSION_SETTINGS` - JSON mapping for suppression/disable controls
- `AGENT_OBS_CONFIG_FILE` - path to a JSON or simple TOML-like config file

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

### 3. Mode selection

The coordinator supports four modes:

- `FULL` - initialize tracing and activate supported instrumentation targets
- `AUGMENT` - reuse an existing provider if present and only add missing capabilities
- `REUSE_EXISTING` - avoid activating standard instrumentors and leave tracing ownership to the app
- `OFF` - do nothing except emit diagnostics

The existing mode-selection logic remains the source of truth; the coordinator extends it by adding planning and actuation after the mode is chosen.

### 4. Instrumentation planning

`agent_obs_runtime.plan` converts the selected mode plus detection signals into an `InstrumentationPlan`.

The plan currently records:

- the selected mode
- provider policy: `initialize`, `reuse`, or `noop`
- whether to enable FastAPI/ASGI ingress instrumentation
- whether to enable `httpx`
- whether to enable `requests`
- whether to enable MCP wrapping
- whether to enable LangChain
- whether to enable LangGraph
- plan warnings

Rules are intentionally simple:

- `FULL` enables supported targets allowed by config and initializes a provider
- `REUSE_EXISTING` reuses the app/provider and skips standard activations
- `AUGMENT` enables only capabilities that appear to be missing
- `OFF` disables all activation

### 5. Actuation

`agent_obs_runtime.actuation` applies the plan safely.

#### Provider behavior

- `initialize` attempts to install a default OpenTelemetry SDK tracer provider and attach a span processor/exporter if the SDK is available
- `reuse` never overrides the existing provider
- `noop` skips provider setup

#### Supported runtime targets

- **FastAPI / ASGI**: prefer `FastAPIInstrumentor`, fall back to `ASGIInstrumentor` when available
- **HTTP egress**: activate `HTTPXClientInstrumentor` and/or `RequestsInstrumentor` conditionally
- **MCP**: apply a lightweight wrapper to a representative tool invocation path
- **LangChain**: prefer the official OpenTelemetry LangChain instrumentor if installed
- **LangGraph**: patch top-level compiled graph execution methods such as `invoke`, `stream`, and `astream`

All activations are wrapped in defensive error handling. The coordinator logs whether each target was enabled, skipped, or failed, along with a reason.

## Diagnostics output

Startup diagnostics are emitted as structured JSON through the `agent_obs_runtime` logger.

The current report includes:

- loaded configuration and config source
- detected tracing and framework signals
- selected mode and selection reason
- instrumentation plan contents
- applied actions
- accumulated warnings

This makes it easy to explain behavior differences across `FULL`, `AUGMENT`, `REUSE_EXISTING`, and `OFF` runs.

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

- it does not rewrite the existing mode-selection logic
- it treats missing optional packages as normal
- it avoids overriding an app-owned provider in reuse modes
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

- `agent_obs_runtime/bootstrap.py` - startup orchestration
- `agent_obs_runtime/config.py` - configuration loading
- `agent_obs_runtime/detection.py` - tracing ownership and framework heuristics
- `agent_obs_runtime/mode.py` - mode selection
- `agent_obs_runtime/plan.py` - instrumentation planning
- `agent_obs_runtime/actuation.py` - plan application
- `agent_obs_runtime/mcp_instrumentation.py` - lightweight MCP wrapping
- `agent_obs_runtime/langchain_langgraph_instrumentation.py` - LangChain/LangGraph support
- `agent_obs_runtime/diagnostics.py` - structured startup reporting
- `src/runtime_coordinator/main.py` - package entrypoint used by the image

## Limitations

This remains a PoC. Notable limitations include:

- no broad framework coverage beyond the small supported set
- heuristic duplicate detection rather than deep certainty
- best-effort provider initialization rather than a production-ready SDK bootstrap story
- minimal monkeypatch-based integrations for MCP and LangGraph
- no operator-driven configuration wiring yet

Those tradeoffs are intentional for this phase: the goal is to demonstrate controlled runtime activation, not a complete production observability platform.
