# Hybrid Solution Design: Configuration + Deferred Ownership Resolution

## Overview

This design combines explicit configuration (for predictable behavior) with lightweight ownership wrappers (for safe, deferred ownership resolution). Together, they solve the sitecustomize timing problem while avoiding brittle instrumentation rollback.

**Key Refinement:** Based on expert feedback, this design **replaces aggressive swap mechanism** (instrument → uninstrument → re-instrument) with **lightweight ownership wrappers** (observe claims → resolve ownership → freeze before first workload). This avoids the fragility of uninstrumentation while preserving the deferred decision-making benefits.

**Critical Assumption:** For any target X (library, framework, component), to avoid double ownership without brittle rollback, the app MUST claim ownership of X before the platform irrevocably activates instrumentation for the first meaningful use of X.

---

## Solution Architecture

### Three-Tier Instrumentation Ownership

```
┌─────────────────────────────────────────────────────────┐
│ Tier 1: Explicit Configuration (Highest Priority)      │
│ ────────────────────────────────────────────────────── │
│ Declared in CR before coordinator runs                 │
│ Example: tracerProvider: "app", fastapi: "platform"    │
│ States immediately set to PLATFORM or APP              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Tier 2: Lightweight Ownership Wrappers (Observe)       │
│ ────────────────────────────────────────────────────── │
│ Observe app instrumentor calls during startup          │
│ Defer deep instrumentation until ownership resolved    │
│ No aggressive uninstrumentation/rollback               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Tier 3: Ownership Freeze (Before First Workload)       │
│ ────────────────────────────────────────────────────── │
│ All UNDECIDED states default to PLATFORM               │
│ Ownership frozen for process lifetime                  │
│ Used when no config and no app claim observed          │
└─────────────────────────────────────────────────────────┘
```

---

## Part 1: Configuration Layer

### 1.1 CRD Schema Extension

Add instrumentation ownership configuration to AgentObservabilityDemo:

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: my-agent
  namespace: demo-apps
spec:
  target:
    # ... existing fields ...

  runtimeCoordinator:
    enabled: true

    # NEW: Instrumentation ownership declaration
    instrumentationOwnership:
      # Who owns the TracerProvider?
      tracerProvider: "platform"  # "platform" | "app" | "auto"

      # Who owns each instrumentor?
      fastapi: "auto"      # "platform" | "app" | "auto"
      httpx: "auto"
      requests: "auto"
      langchain: "auto"
      langgraph: "auto"
      mcp: "auto"

      # Global policy (optional shorthand)
      defaultOwnership: "auto"  # Applied to any not explicitly listed

    # NEW: Provider configuration (Option 2 - env-based config)
    # Used when tracerProvider: "platform" but app needs custom config
    providerConfig:
      endpoint: "http://collector:4318"
      protocol: "http/protobuf"  # or "grpc"
      headers:
        authorization: "Bearer ${SECRET_TOKEN}"
      resourceAttributes:
        service.version: "1.0.0"
        deployment.environment: "prod"
      sampler: "parentbased_traceidratio"  # or "always_on", "always_off", etc.
      samplerArg: "0.1"  # sampler-specific argument

    # NEW: Span buffering (Option 3 - only when tracerProvider: "app")
    # Buffers spans created before app sets provider to avoid data loss
    spanBuffering:
      enabled: false           # Enable buffering mechanism
      maxBufferSize: 1000      # Max spans to buffer (prevents OOM)
      bufferTimeoutMs: 30000   # Flush after timeout even without provider
```

**Ownership Values:**
- `platform`: Coordinator instruments, app should NOT instrument
- `app`: Coordinator skips, app MUST instrument
- `auto`: Coordinator makes decision + swap mechanism active (default)

### 1.2 Configuration Propagation

**Operator side** (`operator/internal/controller/agentobservability_controller.go`):
```go
func buildRuntimeCoordinatorConfig(demo *AgentObservabilityDemo) map[string]interface{} {
    config := map[string]interface{}{
        "enabled": demo.Spec.RuntimeCoordinator.Enabled,
        "instrumentationOwnership": map[string]string{
            "tracerProvider": getOwnership(demo, "tracerProvider", "platform"),
            "fastapi":        getOwnership(demo, "fastapi", "auto"),
            "httpx":          getOwnership(demo, "httpx", "auto"),
            "requests":       getOwnership(demo, "requests", "auto"),
            "langchain":      getOwnership(demo, "langchain", "auto"),
            "langgraph":      getOwnership(demo, "langgraph", "auto"),
            "mcp":            getOwnership(demo, "mcp", "auto"),
        },
    }
    return config
}
```

**Runtime coordinator side** (`runtime-coordinator/agent_obs_runtime/bootstrap.py`):
```python
def _load_config() -> dict[str, Any]:
    config = {
        "enabled": True,
        "ownership": {
            "tracerProvider": "platform",
            "fastapi": "auto",
            "httpx": "auto",
            # ... etc
        }
    }

    # Load from mounted ConfigMap
    config_file = os.getenv("AGENT_OBS_CONFIG_FILE")
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            file_config = yaml.safe_load(f)
            if "instrumentationOwnership" in file_config:
                config["ownership"].update(file_config["instrumentationOwnership"])

    return config
```

### 1.3 Configuration-Driven Decisions

Update decision logic to respect configuration:

```python
def should_initialize_provider(detection: DetectionResult, config: dict) -> bool:
    ownership = config.get("ownership", {}).get("tracerProvider", "platform")

    if ownership == "app":
        # App owns it - skip
        return False
    elif ownership == "platform":
        # Platform owns it - init if not configured
        return not detection.has_configured_provider
    else:  # "auto"
        # Use detection logic + swap will catch app override
        return not detection.has_configured_provider

def should_instrument_fastapi(detection: DetectionResult, config: dict) -> bool:
    ownership = config.get("ownership", {}).get("fastapi", "auto")

    if ownership == "app":
        # App owns it - skip
        return False
    elif ownership == "platform":
        # Platform owns it - instrument if available and not already done
        return detection.fastapi_available and not detection.fastapi_instrumented
    else:  # "auto"
        # Use detection logic + swap will catch app instrumentation
        return detection.fastapi_available and not detection.fastapi_instrumented
```

---

## Part 2: Lightweight Ownership Resolution

### 2.0 Critical Assumption

**FUNDAMENTAL CONSTRAINT:**

> For any target X (library, framework, component), to avoid double ownership without brittle rollback, the app MUST claim ownership of X before the platform irrevocably activates instrumentation for the first meaningful use of X.

This constraint is what makes the deferred ownership approach safe and reliable.

**What this means in practice:**

- ✅ **Safe**: App imports FastAPI, then calls `FastAPIInstrumentor().instrument()` before first request
- ✅ **Safe**: App imports httpx, then instruments it before making first HTTP call
- ❌ **Unsafe**: First HTTP request happens, then app tries to instrument httpx mid-flight

**Why this assumption holds for Python apps:**

1. **sitecustomize runs before main.py** - coordinator installs ownership wrappers early
2. **App startup is sequential** - import → configure → instrument → start server/event loop
3. **First meaningful use is late** - requests don't arrive until `uvicorn.run()`, HTTP calls don't happen until app code runs

**Ownership freeze point:** Before first request/call/graph execution (whichever comes first for each library).

**What we do NOT support:** Runtime ownership handoff during active workload. Once frozen, ownership is permanent for the process lifetime.

---

### 2.1 Ownership State Machine

Each library/framework has an ownership state that evolves during startup:

```python
# runtime-coordinator/agent_obs_runtime/ownership.py

from enum import Enum
from typing import Dict, Optional
import logging

LOGGER = logging.getLogger(__name__)


class OwnershipState(Enum):
    """Ownership states for each instrumentation target."""
    UNDECIDED = "undecided"     # Initial state - not yet resolved
    PLATFORM = "platform"        # Platform owns - emit platform spans
    APP = "app"                  # App owns - no-op in platform wrappers
    FROZEN = "frozen"            # Ownership frozen (no longer UNDECIDED)


class OwnershipResolver:
    """Tracks and resolves ownership for each instrumentation target."""

    def __init__(self, config: dict):
        self.config = config
        self.ownership_config = config.get("ownership", {})

        # Initialize all targets as UNDECIDED
        self.states: Dict[str, OwnershipState] = {
            "tracerProvider": OwnershipState.UNDECIDED,
            "fastapi": OwnershipState.UNDECIDED,
            "httpx": OwnershipState.UNDECIDED,
            "requests": OwnershipState.UNDECIDED,
            "langchain": OwnershipState.UNDECIDED,
            "langgraph": OwnershipState.UNDECIDED,
            "mcp": OwnershipState.UNDECIDED,
        }

        # Apply explicit config immediately
        self._apply_explicit_config()

    def _apply_explicit_config(self):
        """Apply explicit ownership declarations from config."""
        for target, configured_owner in self.ownership_config.items():
            if configured_owner == "platform":
                self.states[target] = OwnershipState.PLATFORM
                LOGGER.info(f"Config declares platform ownership: {target}")
            elif configured_owner == "app":
                self.states[target] = OwnershipState.APP
                LOGGER.info(f"Config declares app ownership: {target}")
            # "auto" leaves state as UNDECIDED

    def observe_app_claim(self, target: str) -> bool:
        """
        Called when app attempts to instrument a target.
        Returns True if app is allowed to proceed, False if denied.
        """
        current_state = self.states.get(target, OwnershipState.UNDECIDED)

        if current_state == OwnershipState.PLATFORM:
            # Config says platform owns - deny app claim
            LOGGER.warning(
                f"App tried to instrument {target} but config declares platform ownership - denied"
            )
            return False

        if current_state == OwnershipState.APP:
            # Already marked as app-owned (or config says app owns)
            LOGGER.info(f"App claiming ownership: {target} (expected)")
            return True

        if current_state == OwnershipState.UNDECIDED:
            # No explicit config - app claim wins
            LOGGER.info(f"App claiming ownership: {target} (auto-detected)")
            self.states[target] = OwnershipState.APP
            return True

        # Frozen - should not happen if timing assumption holds
        LOGGER.error(f"App tried to claim {target} after ownership frozen - denied")
        return False

    def observe_platform_activation(self, target: str):
        """
        Called when platform is about to activate instrumentation.
        Only proceeds if state is UNDECIDED or PLATFORM.
        """
        current_state = self.states.get(target, OwnershipState.UNDECIDED)

        if current_state == OwnershipState.APP:
            LOGGER.debug(f"Skipping platform instrumentation for {target} (app owns)")
            return False

        if current_state in (OwnershipState.UNDECIDED, OwnershipState.PLATFORM):
            LOGGER.info(f"Platform activating instrumentation: {target}")
            self.states[target] = OwnershipState.PLATFORM
            return True

        return False

    def finalize(self):
        """
        Freeze all UNDECIDED states before first workload.
        Called before first request/call/execution.
        """
        for target, state in self.states.items():
            if state == OwnershipState.UNDECIDED:
                # Default to platform ownership if still undecided
                self.states[target] = OwnershipState.PLATFORM
                LOGGER.info(f"Finalized ownership (defaulted to platform): {target}")
            else:
                LOGGER.info(f"Finalized ownership: {target} = {state.value}")

    def get_state(self, target: str) -> OwnershipState:
        """Get current ownership state for a target."""
        return self.states.get(target, OwnershipState.UNDECIDED)

    def is_platform_owned(self, target: str) -> bool:
        """Check if platform owns this target."""
        return self.states.get(target) == OwnershipState.PLATFORM


# Global resolver instance (created during bootstrap)
_resolver: Optional[OwnershipResolver] = None


def get_resolver() -> OwnershipResolver:
    """Get the global ownership resolver."""
    if _resolver is None:
        raise RuntimeError("OwnershipResolver not initialized - call bootstrap() first")
    return _resolver
```

---

### 2.2 Lightweight Ownership Wrappers

Instead of deep instrumentation followed by rollback, install **lightweight wrappers** that observe ownership claims and defer deep instrumentation:

```python
# runtime-coordinator/agent_obs_runtime/ownership_wrappers.py

import threading
from typing import Callable
import logging

LOGGER = logging.getLogger(__name__)

_coordinator_context = threading.local()


def _in_coordinator_context() -> bool:
    """Check if current call is from coordinator."""
    return getattr(_coordinator_context, 'is_coordinator', False)


def install_ownership_wrappers():
    """
    Install lightweight wrappers to observe ownership claims.
    Does NOT deep-instrument - just wraps the instrumentor APIs.
    """
    _wrap_fastapi_instrumentor()
    _wrap_httpx_instrumentor()
    _wrap_requests_instrumentor()
    # Note: langchain, langgraph, mcp require explicit config (too complex for auto)


def _wrap_fastapi_instrumentor():
    """Wrap FastAPIInstrumentor to observe ownership claims."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from agent_obs_runtime.ownership import get_resolver

        original_instrument = FastAPIInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            resolver = get_resolver()

            if _in_coordinator_context():
                # This is coordinator - check if we should proceed
                if resolver.observe_platform_activation("fastapi"):
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.info("Skipping FastAPI instrumentation (app owns)")
                    return None
            else:
                # This is app - observe claim
                if resolver.observe_app_claim("fastapi"):
                    LOGGER.info("App instrumenting FastAPI")
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App FastAPI instrumentation denied (platform owns)")
                    # Return without instrumenting - platform already did it
                    return None

        FastAPIInstrumentor.instrument = ownership_aware_instrument

    except ImportError:
        LOGGER.debug("FastAPI not available, skipping wrapper")


def _wrap_httpx_instrumentor():
    """Wrap HTTPXClientInstrumentor to observe ownership claims."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from agent_obs_runtime.ownership import get_resolver

        original_instrument = HTTPXClientInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            resolver = get_resolver()

            if _in_coordinator_context():
                if resolver.observe_platform_activation("httpx"):
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.info("Skipping httpx instrumentation (app owns)")
                    return None
            else:
                if resolver.observe_app_claim("httpx"):
                    LOGGER.info("App instrumenting httpx")
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App httpx instrumentation denied (platform owns)")
                    return None

        HTTPXClientInstrumentor.instrument = ownership_aware_instrument

    except ImportError:
        LOGGER.debug("httpx not available, skipping wrapper")


def _wrap_requests_instrumentor():
    """Wrap RequestsInstrumentor to observe ownership claims."""
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from agent_obs_runtime.ownership import get_resolver

        original_instrument = RequestsInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            resolver = get_resolver()

            if _in_coordinator_context():
                if resolver.observe_platform_activation("requests"):
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.info("Skipping requests instrumentation (app owns)")
                    return None
            else:
                if resolver.observe_app_claim("requests"):
                    LOGGER.info("App instrumenting requests")
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App requests instrumentation denied (platform owns)")
                    return None

        RequestsInstrumentor.instrument = ownership_aware_instrument

    except ImportError:
        LOGGER.debug("requests not available, skipping wrapper")
```

---

### 2.3 Bootstrap Integration

```python
# runtime-coordinator/agent_obs_runtime/bootstrap.py

from agent_obs_runtime.ownership import OwnershipResolver, _resolver
from agent_obs_runtime.ownership_wrappers import install_ownership_wrappers, _coordinator_context

def bootstrap(config: dict[str, Any] | None = None) -> None:
    if config is None:
        config = _load_config()

    # 1. Create ownership resolver
    global _resolver
    _resolver = OwnershipResolver(config)

    # 2. Install lightweight wrappers FIRST (before any instrumentation)
    install_ownership_wrappers()

    # 3. Handle provider ownership
    provider_ownership = _resolver.get_state("tracerProvider")
    if provider_ownership == OwnershipState.APP:
        # App owns provider - optionally enable span buffering
        if config.get("spanBuffering", {}).get("enabled", False):
            install_span_buffering()
        else:
            LOGGER.warning("App owns TracerProvider but span buffering disabled - early spans may be lost")
    else:
        # Platform owns provider - initialize it
        if _resolver.observe_platform_activation("tracerProvider"):
            initialize_tracer_provider(config)

    # 4. Run detection
    detection = detect_state()

    # 5. Set coordinator context flag
    _coordinator_context.is_coordinator = True

    try:
        # Make instrumentation decisions
        # Wrappers will check ownership resolver before proceeding

        if should_instrument_fastapi(detection, config):
            instrument_fastapi()  # Wrapper checks ownership

        if should_instrument_httpx(detection, config):
            instrument_httpx()  # Wrapper checks ownership

        if should_instrument_requests(detection, config):
            instrument_requests()  # Wrapper checks ownership

        # For complex frameworks, require explicit config
        if config.get("ownership", {}).get("langchain") == "platform":
            instrument_langchain()

        if config.get("ownership", {}).get("langgraph") == "platform":
            instrument_langgraph()

        if config.get("ownership", {}).get("mcp") == "platform":
            instrument_mcp()

    finally:
        # Clear coordinator flag
        _coordinator_context.is_coordinator = False

    # 6. Finalize ownership before first workload
    # This happens automatically before first request in most apps
    # But we can also schedule it for safety
    _schedule_ownership_freeze()

    _emit_diagnostics(_resolver, detection, config)


def _schedule_ownership_freeze():
    """
    Schedule ownership freeze before first meaningful workload.
    For FastAPI apps, we can hook into app startup.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        # If FastAPI is instrumented, hook into app startup
        # This ensures freeze happens before first request
        original_instrument_app = FastAPIInstrumentor.instrument_app

        def freeze_aware_instrument_app(app, **kwargs):
            result = original_instrument_app(app, **kwargs)

            # Add startup event to freeze ownership
            @app.on_event("startup")
            async def freeze_ownership():
                _resolver.finalize()
                LOGGER.info("Ownership frozen before first request")

            return result

        FastAPIInstrumentor.instrument_app = staticmethod(freeze_aware_instrument_app)

    except ImportError:
        # Not a FastAPI app - freeze after bootstrap
        _resolver.finalize()
        LOGGER.info("Ownership frozen at end of bootstrap")
```

---

### 2.4 Ownership Resolution Lifecycle

The complete lifecycle from process start to first workload:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Process Start                                            │
│ ─────────────────────────────────────────────────────────── │
│ Python interpreter starts, processes sitecustomize.py       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. sitecustomize (Coordinator Bootstrap)                    │
│ ─────────────────────────────────────────────────────────── │
│ • Create OwnershipResolver with config                      │
│ • Install lightweight wrappers (no deep instrumentation)    │
│ • Handle provider ownership                                 │
│ • Run detection                                             │
│ • Make preliminary instrumentation decisions                │
│ • Wrappers observe ownership claims                         │
│                                                              │
│ State: All targets start UNDECIDED or per config            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. App Import Phase (main.py starts)                        │
│ ─────────────────────────────────────────────────────────── │
│ • App imports libraries (FastAPI, httpx, etc.)              │
│ • App may call instrumentor APIs                            │
│ • Wrappers observe app claims                               │
│ • States transition: UNDECIDED → APP (if claimed)           │
│                                                              │
│ State: Some targets now APP, others still UNDECIDED         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Ownership Freeze (Before First Workload)                 │
│ ─────────────────────────────────────────────────────────── │
│ • Triggered by app startup event (FastAPI on_event)         │
│ • Or automatically at end of bootstrap if no hook           │
│ • All UNDECIDED states default to PLATFORM                  │
│ • Ownership now FROZEN for process lifetime                 │
│                                                              │
│ State: All targets either PLATFORM or APP (frozen)          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Runtime (Requests/Calls/Executions)                      │
│ ─────────────────────────────────────────────────────────── │
│ • First request arrives / first HTTP call / first graph run │
│ • Instrumentation emits spans based on ownership            │
│ • Platform-owned: platform spans emitted                    │
│ • App-owned: app spans emitted (or no-op in wrappers)       │
│                                                              │
│ State: Frozen - no more ownership changes                   │
└─────────────────────────────────────────────────────────────┘
```

**Key Timing Guarantee:**

The critical assumption holds because:
- Phase 2 (sitecustomize) installs wrappers before app code runs
- Phase 3 (app import) is when app claims ownership
- Phase 4 (freeze) happens before Phase 5 (first workload)
- **App has all of Phase 3 to claim ownership before instrumentation is used**

---

### 2.5 Per-Library Scoping

Not all libraries are equal. Different instrumentation complexity requires different strategies:

#### Tier 1: Lightweight Wrappers Work Well

**Libraries:** `requests`, `httpx`

**Strategy:** Full ownership wrapper support

**Why:** Simple monkeypatch-based instrumentation, clean instrument/uninstrument, no persistent state

**Implementation:** Install wrappers, observe claims, respect ownership

---

#### Tier 2: Early Detection Required

**Libraries:** `fastapi` (ASGI frameworks)

**Strategy:** Ownership wrappers + early freeze

**Why:** Middleware registration and app object wrapping make late changes risky

**Implementation:**
- Wrapper observes claims
- Freeze ownership before `app = FastAPI()` completes
- No instrumentation activation during request handling

**Constraint:** App must instrument FastAPI before calling `uvicorn.run()` or before first request

---

#### Tier 3: Configuration-Only (No Auto-Detection)

**Libraries:** `langchain`, `langgraph`, `mcp`

**Strategy:** Require explicit config declaration

**Why:**
- Complex callback systems
- Stateful client/server patterns
- Persistent framework state
- Too risky for deferred ownership

**Implementation:**
- If config says `"platform"` → coordinator instruments
- If config says `"app"` → coordinator skips
- If config says `"auto"` or missing → **coordinator skips** (safe default)

**Documentation:** Clear guidance that these require explicit ownership declaration

---

### 2.6 Example Scenarios

#### Scenario 1: Zero Config, No App Instrumentation

```
sitecustomize: Install wrappers, states = UNDECIDED
               Coordinator calls instrument_fastapi()
               → Wrapper sees coordinator context
               → observe_platform_activation("fastapi") → True
               → Deep instrumentation proceeds
               → State: fastapi = PLATFORM

main.py:       App doesn't call instrumentor APIs
               App starts server

Freeze:        All UNDECIDED → PLATFORM

Result:        Platform owns all instrumentation ✓
```

---

#### Scenario 2: Zero Config, App Instruments

```
sitecustomize: Install wrappers, states = UNDECIDED
               Coordinator calls instrument_httpx()
               → Wrapper sees coordinator context
               → observe_platform_activation("httpx") → True
               → State: httpx = PLATFORM

main.py:       from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
               HTTPXClientInstrumentor().instrument()
               → Wrapper sees app context (not coordinator)
               → observe_app_claim("httpx") → False (platform already activated)
               → Wrapper denies app claim, logs warning
               → App's instrument() returns without effect

Freeze:        States frozen

Result:        Platform owns httpx (app claim denied) ⚠️
               Warning logged but no crash
```

---

#### Scenario 3: Config Says "app", App Instruments

```
sitecustomize: Install wrappers
               Config: ownership.fastapi = "app"
               → State: fastapi = APP (from config)
               Coordinator calls instrument_fastapi()
               → Wrapper sees coordinator context
               → observe_platform_activation("fastapi") → False (APP state)
               → Wrapper skips, logs "app owns"
               → No deep instrumentation

main.py:       from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
               FastAPIInstrumentor().instrument()
               → Wrapper sees app context
               → observe_app_claim("fastapi") → True (already APP)
               → Deep instrumentation proceeds

Freeze:        States frozen

Result:        App owns fastapi ✓
```

---

#### Scenario 4: Config Says "platform", App Tries to Instrument

```
sitecustomize: Install wrappers
               Config: ownership.requests = "platform"
               → State: requests = PLATFORM (from config)
               Coordinator calls instrument_requests()
               → Wrapper sees coordinator context
               → observe_platform_activation("requests") → True (config says platform)
               → Deep instrumentation proceeds

main.py:       from opentelemetry.instrumentation.requests import RequestsInstrumentor
               RequestsInstrumentor().instrument()
               → Wrapper sees app context
               → observe_app_claim("requests") → False (PLATFORM state)
               → Wrapper denies, logs warning
               → No effect

Freeze:        States frozen

Result:        Platform owns requests (config enforced) ✓
               App's attempt denied as expected
```

---

## Part 3: TracerProvider Special Handling

### 3.1 The Provider Lock-In Problem

**Critical constraint:** OpenTelemetry allows TracerProvider to be set only ONCE.

**Implication:** Whoever initializes first (coordinator in sitecustomize) locks the provider.

### 3.2 Three Approaches to Provider Ownership

Apps needing custom provider configuration have three options, in order of preference:

#### Option 1: Platform-Owned (Default, Simplest)

```yaml
spec:
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "platform"  # or omit (default)
```

**Behavior:**
- Coordinator initializes provider with operator-configured settings
- App cannot override provider in code
- All instrumentation uses platform provider

**Use when:** Standard platform configuration is sufficient.

---

#### Option 2: Platform-Owned with Env-Based App Configuration (Recommended for Custom Config)

```yaml
spec:
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "platform"
    providerConfig:
      # Operator writes these as env vars
      endpoint: "http://custom-collector:4318"
      headers:
        authorization: "Bearer ${SECRET_TOKEN}"
      resourceAttributes:
        deployment.environment: "production"
```

**Behavior:**
- Coordinator initializes provider BUT respects operator-configured env vars
- App's provider initialization code (if any) is silently ignored due to set-once
- Standard OpenTelemetry env vars take precedence
- App removes provider initialization from code, relies on env configuration

**Implementation:**

```python
def initialize_tracer_provider(config: dict) -> None:
    # Coordinator sets env vars from operator config BEFORE initializing provider
    # This allows OTel SDK auto-configuration to pick them up

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource

    # OTel SDK reads these env vars automatically:
    # OTEL_EXPORTER_OTLP_ENDPOINT
    # OTEL_EXPORTER_OTLP_HEADERS
    # OTEL_RESOURCE_ATTRIBUTES
    # OTEL_TRACES_SAMPLER

    # Merge operator config with env vars (env vars take precedence)
    resource_attrs = {}
    if "service_name" in config:
        resource_attrs["service.name"] = config["service_name"]

    # OTel SDK reads OTEL_RESOURCE_ATTRIBUTES automatically and merges
    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)

    # Exporter setup respects OTEL_EXPORTER_OTLP_* env vars
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter()  # Reads from env vars
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
```

**Use when:** App needs custom provider config but can move it from code to YAML/env vars.

---

#### Option 3: App-Owned with Span Buffering (Complex, Last Resort)

```yaml
spec:
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "app"  # Coordinator won't initialize
    spanBuffering:
      enabled: true           # Buffer spans until app sets provider
      maxBufferSize: 1000     # Prevent OOM
      bufferTimeoutMs: 30000  # Flush after timeout even if no provider
```

**Behavior:**
- Coordinator skips `initialize_tracer_provider()`
- Coordinator instruments frameworks (FastAPI, httpx, etc.) as configured
- **Coordinator patches tracing APIs to buffer spans** instead of no-op
- App initializes provider in main.py
- When `set_tracer_provider()` is called, buffered spans are flushed through the new provider
- All instrumentation (platform or app) uses app's provider

**The Early Span Problem:**

Without buffering, spans created between sitecustomize and main.py are lost:

```
sitecustomize: coordinator instruments FastAPI/httpx (no provider set)
import time:   some library makes HTTP call → span created with ProxyTracerProvider
               ProxyTracerProvider creates no-op span → data lost
main.py:       app calls set_tracer_provider(my_provider)
               Previous spans already lost, cannot be recovered
```

**Solution: Span Buffering Mechanism**

```python
# runtime-coordinator/agent_obs_runtime/span_buffer.py

import threading
import time
from typing import List, Dict, Any
from opentelemetry import trace

_buffered_span_data: List[Dict[str, Any]] = []
_buffer_lock = threading.Lock()
_max_buffer_size = 1000
_buffer_timeout_ns = 30_000_000_000  # 30 seconds in nanoseconds
_buffer_start_time = time.time_ns()

class BufferingProxyTracer:
    """Tracer that buffers span data instead of creating no-op spans."""

    def __init__(self, name: str, version: str = None):
        self._name = name
        self._version = version

    def start_span(self, name: str, context=None, **kwargs):
        return LazySpan(
            name=name,
            tracer_name=self._name,
            tracer_version=self._version,
            context=context,
            **kwargs
        )

class LazySpan:
    """Span that buffers its data instead of exporting immediately."""

    def __init__(self, name, tracer_name, tracer_version=None, context=None, **kwargs):
        self.name = name
        self.tracer_name = tracer_name
        self.tracer_version = tracer_version
        self.context = context
        self.start_time = time.time_ns()
        self.attributes = kwargs.get('attributes', {})
        self.kind = kwargs.get('kind')
        self.events = []
        self.links = kwargs.get('links', [])

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None, timestamp=None):
        self.events.append({
            'name': name,
            'attributes': attributes or {},
            'timestamp': timestamp or time.time_ns()
        })

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time_ns()
        self.exception = exc_val

        # Buffer the span data
        with _buffer_lock:
            if len(_buffered_span_data) < _max_buffer_size:
                _buffered_span_data.append({
                    'name': self.name,
                    'tracer_name': self.tracer_name,
                    'tracer_version': self.tracer_version,
                    'context': self.context,
                    'start_time': self.start_time,
                    'end_time': self.end_time,
                    'attributes': self.attributes.copy(),
                    'events': self.events.copy(),
                    'links': self.links.copy(),
                    'kind': self.kind,
                    'exception': self.exception,
                })
            # else: silently drop span if buffer full (prevents OOM)

def install_span_buffering():
    """Patch tracing APIs to buffer spans instead of no-op."""

    # Patch ProxyTracerProvider to return buffering tracers
    original_get_tracer = trace._ProxyTracerProvider.get_tracer

    def buffering_get_tracer(self, name, version=None, schema_url=None):
        return BufferingProxyTracer(name, version)

    trace._ProxyTracerProvider.get_tracer = buffering_get_tracer

    # Patch set_tracer_provider to flush buffer
    original_set_tracer_provider = trace.set_tracer_provider

    def flushing_set_tracer_provider(provider):
        # Flush buffered spans through the new provider
        with _buffer_lock:
            if _buffered_span_data:
                _flush_buffered_spans(provider)
            _buffered_span_data.clear()

        # Now set the provider (this is the first set, so it succeeds)
        return original_set_tracer_provider(provider)

    trace.set_tracer_provider = flushing_set_tracer_provider

def _flush_buffered_spans(provider):
    """Create real spans from buffered data and export them."""
    from opentelemetry.sdk.trace import Span
    from opentelemetry.trace import SpanContext, TraceFlags

    for data in _buffered_span_data:
        # Get tracer from the new provider
        tracer = provider.get_tracer(
            data['tracer_name'],
            data['tracer_version']
        )

        # Create a real span with buffered data
        # Note: This is a simplified version - real implementation needs
        # to handle context propagation, parent-child relationships, etc.
        span = tracer.start_span(
            data['name'],
            context=data['context'],
            kind=data['kind'],
            attributes=data['attributes'],
            links=data['links'],
            start_time=data['start_time']
        )

        # Add buffered events
        for event in data['events']:
            span.add_event(
                event['name'],
                attributes=event['attributes'],
                timestamp=event['timestamp']
            )

        # End span with original timestamp
        span.end(end_time=data['end_time'])

        # Span will be exported through provider's processors
```

**Integration in Bootstrap:**

```python
from agent_obs_runtime.span_buffer import install_span_buffering

def bootstrap(config: dict[str, Any] | None = None) -> None:
    if config is None:
        config = _load_config()

    # Check provider ownership
    provider_ownership = config.get("ownership", {}).get("tracerProvider", "platform")

    if provider_ownership == "app":
        # Install span buffering BEFORE any instrumentation
        if config.get("spanBuffering", {}).get("enabled", False):
            install_span_buffering()
            _logger.info("Span buffering enabled - spans will be buffered until app sets provider")
        else:
            _logger.warning(
                "tracerProvider: app without span buffering - "
                "spans created before app's set_tracer_provider() will be lost"
            )
    else:
        # Platform owns provider - initialize it now
        initialize_tracer_provider(config)

    # Install swap mechanism
    install_swap_mechanism()

    # Proceed with instrumentation decisions...
```

**Limitations and Risks:**

⚠️ **Buffer overflow**: If app never sets provider, buffer grows until `maxBufferSize` then silently drops spans
⚠️ **Memory usage**: Buffered spans consume memory (mitigated by size limit)
⚠️ **Context complexity**: Parent-child relationships require careful handling during flush
⚠️ **Implementation complexity**: More intricate than other options
⚠️ **Timing-dependent**: Buffer timeout may flush before app sets provider

**Use when:** App absolutely must initialize provider in code AND cannot move config to env vars.

---

### 3.3 Decision Matrix

| Scenario | Recommended Option | Rationale |
|----------|-------------------|-----------|
| App has no custom provider needs | Option 1 (Platform-Owned) | Simplest, zero config |
| App needs custom endpoint/sampling | Option 2 (Env-Based) | Standard OTel pattern, no buffering complexity |
| App needs custom exporter class | Option 3 (Buffering) | Can't achieve via env vars alone |
| App initializes provider in code | Option 2 or 3 | Option 2: move to env, Option 3: use buffering |

**Strong Recommendation:** Prefer Option 2 over Option 3 whenever possible. Moving provider configuration from code to env vars is a small refactor with large reliability gains.

---

## Implementation Plan

### Phase 1: Configuration Layer (Week 1)

**Tasks:**
1. Update CRD schema with `instrumentationOwnership` and `providerConfig` fields
2. Update operator controller to pass ownership config to coordinator
3. Update coordinator to read ownership config
4. Modify decision functions to respect config
5. Implement env-based provider configuration (Option 2)
6. Add tests for config-driven decisions

**Deliverable:** Config-based ownership control works with env-based provider configuration

---

### Phase 1.5: Span Buffering (Optional, Week 1.5)

**Tasks:**
1. Create `span_buffer.py` module with buffering implementation
2. Implement `BufferingProxyTracer` and `LazySpan` classes
3. Patch `ProxyTracerProvider.get_tracer` for buffering
4. Patch `set_tracer_provider` to flush buffered spans
5. Add buffer size limits and timeout handling
6. Integrate buffering into bootstrap based on config
7. Add tests for buffering and flush scenarios

**Deliverable:** Span buffering works when `tracerProvider: app` and `spanBuffering.enabled: true`

**Note:** This phase is optional and only needed for apps that cannot use env-based configuration (Option 2). Most use cases should prefer env-based configuration over span buffering.

---

### Phase 2: Lightweight Ownership Wrappers (Week 2)

**Tasks:**
1. Create `ownership.py` module with state machine (`OwnershipResolver`, `OwnershipState`)
2. Create `ownership_wrappers.py` module with lightweight wrappers
3. Implement wrappers for FastAPI, httpx, requests (observe claims, defer deep instrumentation)
4. Add coordinator context flag management
5. Implement ownership freeze before first workload
6. Add per-library scoping (Tier 1: wrappers, Tier 2: early detection, Tier 3: config-only)
7. Test ownership resolution lifecycle and state transitions

**Deliverable:** Lightweight ownership wrappers observe claims and resolve ownership before first workload

**Critical Constraint Validation:** Ensure timing assumption holds - app must claim ownership before first meaningful use of each library

---

### Phase 3: Integration & Testing (Week 3)

**Tasks:**
1. Test combined config + ownership wrapper scenarios
2. Test all three provider ownership options (platform, env-based, buffering)
3. Validate critical timing assumption across different app patterns
4. Update demo apps to test different ownership models:
   - Zero config (all platform)
   - Explicit config (mixed ownership)
   - App claims ownership (auto-detected)
   - Complex frameworks (config-only)
5. Update verification scripts to check ownership state and freeze timing
6. Document usage, limitations, and timing assumptions
7. Add operator-level validation for config correctness

**Deliverable:** End-to-end working hybrid solution with ownership wrappers and all three provider options

**Validation Focus:** Confirm timing assumption holds in realistic app patterns (FastAPI startup, async frameworks, import-time side effects)

---

## Usage Examples

### Example 1: Zero Config (Default)

```yaml
# No ownership config - all "auto"
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: simple-agent
spec:
  target:
    workloadName: my-agent
```

**Behavior:**
- Coordinator installs ownership wrappers
- All states start as UNDECIDED
- Coordinator activates instrumentation (states → PLATFORM)
- App doesn't claim ownership
- Ownership frozen before first request
- TracerProvider initialized by coordinator
- All spans emitted by platform instrumentation

---

### Example 2: App Configures Provider via Env Vars (Recommended)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: custom-config-agent
spec:
  target:
    workloadName: my-agent
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "platform"  # Coordinator initializes
    providerConfig:
      endpoint: "http://custom-collector.observability:4318"
      headers:
        authorization: "Bearer ${OTEL_AUTH_TOKEN}"
      resourceAttributes:
        deployment.environment: "production"
        service.version: "1.2.3"
      sampler: "parentbased_traceidratio"
      samplerArg: "0.1"  # 10% sampling
```

**Behavior:**
- Coordinator initializes provider with operator-provided config
- Config written as `OTEL_*` env vars before provider initialization
- App's provider initialization code (if any) silently ignored due to set-once
- App removes provider init from code, relies on declarative config
- All instrumentation uses platform-initialized provider with app's config

**App migration:**
```python
# BEFORE (in app code):
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://custom-collector:4318")
))
trace.set_tracer_provider(provider)

# AFTER (remove from code, declare in YAML):
# Just delete the provider initialization - config comes from CR
```

---

### Example 3: App Owns Provider with Span Buffering (Last Resort)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: app-owned-provider
spec:
  target:
    workloadName: my-agent
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "app"  # Coordinator won't initialize
    spanBuffering:
      enabled: true
      maxBufferSize: 1000
      bufferTimeoutMs: 30000
```

**Behavior:**
- Coordinator skips provider initialization
- Coordinator instruments frameworks (FastAPI, httpx, etc.)
- Spans created before app's `set_tracer_provider()` are buffered
- App initializes provider in main.py
- When provider is set, buffered spans are flushed and exported
- All instrumentation uses app's provider

**Use only when:**
- App needs custom exporter class not configurable via env vars
- App absolutely cannot move provider config from code to YAML
- Understanding that this adds complexity and risk (buffer limits, timing)

---

### Example 4: Mixed Ownership

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: partial-control-agent
spec:
  target:
    workloadName: my-agent
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "platform"  # Platform handles backend
      fastapi: "app"               # App wants custom FastAPI hooks
      httpx: "platform"            # Platform handles httpx
      langchain: "auto"            # Let swap mechanism decide
```

**Behavior:**
- Coordinator initializes provider
- Coordinator skips FastAPI (app will handle)
- Coordinator instruments httpx
- Coordinator tries LangChain, swap catches if app also does

---

## Limitations & Trade-offs

### Limitation 1: TracerProvider Lock-In

**What:** Once initialized (by coordinator or app), provider cannot be changed

**Impact:** If coordinator initializes provider, app cannot override backend config in code

**Mitigation:** Three options available:
1. **Option 1 (Default)**: Use platform-owned provider with operator defaults
2. **Option 2 (Recommended)**: Use platform-owned provider with env-based app config (declared in CR)
3. **Option 3 (Last Resort)**: Use app-owned provider with span buffering (complex)

**Acceptable:** Yes - this is an OpenTelemetry constraint, not our design flaw

---

### Limitation 2: Env-Based Config Preferred Over Code-Based

**What:** App-owned provider (Option 3) requires complex span buffering mechanism

**Impact:** Apps wanting custom provider config should use Option 2 (env-based) instead of Option 3 (code-based)

**Mitigation:**
- Document env-based configuration as strongly recommended path
- Provide clear migration guide from code-based to env-based config
- Make span buffering opt-in (disabled by default)

**Acceptable:** Yes - env-based config is standard OpenTelemetry practice and simpler than buffering

---

### Limitation 3: Span Buffering Complexity and Risks

**What:** When using app-owned provider with buffering (Option 3), several risks apply

**Impact:**
- Buffer has size limit - spans dropped if app doesn't set provider in time
- Buffer has timeout - may flush before app sets provider
- Context propagation adds complexity to span flush
- Memory usage grows with buffered spans

**Mitigation:**
- Configurable buffer size and timeout
- Clear warnings in logs when buffering is active
- Strong recommendation to use Option 2 instead

**Acceptable:** Yes - complexity is acceptable for rare edge case; most apps use Option 2

---

### Limitation 4: Timing Assumption for Ownership Resolution

**What:** Critical assumption - app must claim ownership before first meaningful use of each library

**Impact:**
- If app instruments a library AFTER platform has already used it (e.g., after first HTTP request), ownership conflict occurs
- If ownership claim happens during in-flight request, race conditions possible
- Ownership cannot change after freeze point

**Mitigation:**
- Document timing assumption clearly
- Freeze ownership before first workload (FastAPI startup event, etc.)
- Provide clear guidance: "instrument in main.py before uvicorn.run()"
- Log warnings if late claims detected
- Complex frameworks (Tier 3) require explicit config to avoid auto-detection timing issues

**Acceptable:** Yes - timing assumption holds in normal Python app startup patterns (import → configure → start server)

---

### Limitation 5: Complex Frameworks Require Explicit Config

**What:** LangChain, LangGraph, MCP require explicit ownership declaration (Tier 3)

**Impact:** Cannot use "auto" detection for these - must declare "platform" or "app" in config

**Mitigation:**
- Clear documentation of Tier 1/2/3 scoping
- Default to skipping instrumentation if not explicitly configured (safe)
- Provide config examples for each framework

**Acceptable:** Yes - these frameworks are too stateful/complex for deferred ownership

---

## Success Criteria

✅ **Zero-config works** - Default behavior instruments everything safely

✅ **App control available** - Apps can declare ownership and customize via three provider options

✅ **No double instrumentation** - Config + ownership wrappers prevent duplicates

✅ **Graceful degradation** - Missing config doesn't break, ownership wrappers observe and resolve

✅ **Clear ownership** - Easy to understand who owns what

✅ **No data loss** - Env-based config (Option 2) solves early span problem without buffering complexity

✅ **Documented limitations** - Provider lock-in and buffering risks are well explained

---

## Conclusion

The refined hybrid solution addresses expert feedback and combines the best approaches:

1. **Configuration** gives predictability and control
2. **Lightweight ownership wrappers** observe claims without brittle uninstrumentation
3. **State machine** tracks ownership resolution (UNDECIDED → PLATFORM/APP → FROZEN)
4. **Deferred ownership** avoids aggressive instrument/uninstrument cycles
5. **Env-based provider config** solves custom config needs without complexity
6. **Span buffering** handles edge cases where code-based init is unavoidable
7. **Per-library scoping** (Tier 1/2/3) matches instrumentation strategy to complexity
8. **Together** they solve the timing problem safely and reliably

**Critical Success Factor:** Timing assumption holds - app claims ownership before first meaningful use.

The TracerProvider limitation is acceptable because:
- It's an OpenTelemetry constraint, not our design flaw
- We provide THREE clear paths for different needs:
  - **Option 1**: Simple default (most apps)
  - **Option 2**: Env-based config (apps with custom needs)
  - **Option 3**: Buffering (rare edge cases)
- Option 2 is strongly recommended over Option 3

The ownership wrapper approach is acceptable because:
- ✅ No brittle uninstrumentation/rollback
- ✅ No in-flight ownership handoff
- ✅ Clean state machine with freeze point
- ✅ Timing assumption holds for normal Python app patterns
- ✅ Scoped to appropriate libraries (Tier 1: wrappers work, Tier 3: config required)

**Recommendation: PROCEED with implementation**

**Implementation Priority:**
1. Phase 1: Configuration Layer + Option 1 and 2 (env-based config)
2. Phase 2: Lightweight Ownership Wrappers (state machine + deferred ownership)
3. Phase 1.5: Span Buffering (Option 3) - **OPTIONAL**, implement only if needed

**Design Changes from Original:**
- ❌ Removed aggressive swap mechanism (instrument → uninstrument → re-instrument)
- ✅ Added lightweight ownership wrappers (observe → resolve → freeze)
- ✅ Added state machine per library
- ✅ Added per-library scoping (Tier 1/2/3)
- ✅ Added critical timing assumption documentation
