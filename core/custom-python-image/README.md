# Custom Python Image

This directory contains the build assets for the custom Python auto-instrumentation image used by this PoC.

## What this image is

The image is a **capability bundle** for Python agent workloads that need OpenTelemetry support without forcing blanket auto-instrumentation.

It packages:

- Python 3.11 on a lightweight `python:3.11-slim` base.
- OpenTelemetry core libraries (`opentelemetry-api`, `opentelemetry-sdk`, and `opentelemetry-exporter-otlp`).
- Curated Python instrumentor packages for FastAPI/ASGI, `httpx`, and `requests`.
- An optional best-effort install of `opentelemetry-instrumentation-langchain` at build time.
- The local `runtime-coordinator` package, exposed as `agent_obs_runtime`.
- A `sitecustomize.py` startup hook that invokes the runtime coordinator as early as Python startup allows.

## How it differs from stock OpenTelemetry Python auto-instrumentation

### Stock OpenTelemetry Python auto-instrumentation

The standard OpenTelemetry Python auto-instrumentation flow typically centers on the `opentelemetry-instrument` launcher and eager startup hooks that activate many supported instrumentors up front.

That model is convenient, but it is **not** what this repository wants.

### This custom image

This image intentionally separates **installed capability** from **runtime activation policy**:

- instrumentation packages are installed into the image
- nothing is automatically instrumented just because the packages exist
- `sitecustomize.py` calls the runtime coordinator
- the runtime coordinator decides which instrumentors to activate, which ones to skip, and whether to reuse an existing tracing setup

This keeps control centralized in the coordinator instead of a blanket startup shim.

## Startup flow

```text
Python start
  -> sitecustomize.py runs
  -> runtime coordinator runs
  -> coordinator detects + plans
  -> coordinator activates selected instrumentors
```

More concretely:

1. Python initializes its normal `site` machinery.
2. `sitecustomize.py` is imported automatically from `site-packages`.
3. `sitecustomize.py` executes:

   ```python
   from agent_obs_runtime.bootstrap import run
   run()
   ```

4. The runtime coordinator:
   - detects existing tracing ownership signals
   - selects `FULL`, `AUGMENT`, `REUSE_EXISTING`, or `OFF`
   - builds an instrumentation plan
   - activates only the selected instrumentors and wrappers
   - logs diagnostics without crashing the application

## Why this design exists

This design exists to support coordination scenarios that stock eager auto-instrumentation handles poorly:

- avoid double instrumentation when the application already owns tracing
- support coexistence with user-managed instrumentation or providers
- enable `AUGMENT`, `REUSE_EXISTING`, and `FULL` coordination modes
- keep instrumentation packages available inside the image without forcing them on every workload
- preserve a standard application startup command so OpenTelemetry Operator injection remains compatible

## Activation model

The activation model is strict:

- the image **contains** instrumentation packages
- the image does **not** call `opentelemetry-instrument`
- the image does **not** call `instrument_all()` or any equivalent blanket activation hook
- the runtime coordinator is the only component that decides what gets turned on

This means the image can serve as the Python auto-instrumentation image in an OpenTelemetry `Instrumentation` resource while still delegating activation policy to the runtime coordinator.

## Build details

### Docker build context

The Dockerfile expects to be built from the repository root so it can copy both the image assets and the local runtime coordinator package.

Example:

```bash
docker build -f custom-python-image/Dockerfile -t agent-obs-python:latest .
```

### Optional LangChain instrumentation

The Dockerfile attempts a best-effort install of `opentelemetry-instrumentation-langchain` when `INCLUDE_LANGCHAIN_INSTRUMENTATION=1` (the default). If that package is unavailable for the selected package index or version set, the build continues and the image still supports the rest of the coordinator-controlled flow.

To skip that optional install entirely:

```bash
docker build \
  -f custom-python-image/Dockerfile \
  --build-arg INCLUDE_LANGCHAIN_INSTRUMENTATION=0 \
  -t agent-obs-python:latest .
```

## Environment configuration

The image keeps environment defaults intentionally small:

- `OTEL_SERVICE_NAME=python-agent` as a soft default that users can override
- `OTEL_EXPORTER_OTLP_ENDPOINT` is expected to be supplied externally when needed
- the runtime coordinator can still change behavior based on its own config and detection logic

The image does **not** hardcode an OTLP endpoint or a conflicting exporter setup.

## OpenTelemetry Operator compatibility

The image is designed to remain compatible with operator-driven injection:

- it keeps the container startup command standard
- it does not replace the user application's entrypoint with a custom shell wrapper
- it relies on Python's built-in `sitecustomize` hook instead of a separate launcher
- it leaves activation decisions to the embedded runtime coordinator

That makes it suitable for use as the Python auto-instrumentation image referenced by an OpenTelemetry `Instrumentation` resource.
