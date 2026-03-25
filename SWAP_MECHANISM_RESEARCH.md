# Swap Mechanism Research - Critical Questions Analysis

## Executive Summary

**Status**: ⚠️ **CRITICAL BLOCKER IDENTIFIED**

The TracerProvider override restriction in OpenTelemetry creates a fundamental incompatibility with the swap mechanism for provider initialization. However, the swap mechanism **CAN WORK** for individual instrumentors (FastAPI, httpx, etc.) if we modify the approach.

---

## Research Findings by Critical Question

### 1. Do instrumentors support clean uninstrumentation?

**Answer: YES ✅**

**Evidence:**
- All instrumentors inherit from `BaseInstrumentor` which provides `uninstrument()` method
- Each instrumentor implements `_uninstrument()` that reverses the `_instrument()` operations
- The `_is_instrumented_by_opentelemetry` flag tracks instrumentation state

**FastAPI Example:**
```python
def _instrument(self, **kwargs):
    self._original_fastapi = fastapi.FastAPI
    _InstrumentedFastAPI._instrument_kwargs = kwargs
    fastapi.FastAPI = _InstrumentedFastAPI

def _uninstrument(self, **kwargs):
    instances_to_uninstrument = list(_InstrumentedFastAPI._instrumented_fastapi_apps)
    for instance in instances_to_uninstrument:
        self.uninstrument_app(instance)
    _InstrumentedFastAPI._instrumented_fastapi_apps.clear()
    fastapi.FastAPI = self._original_fastapi
```

**httpx Example:**
```python
def _instrument(self, **kwargs):
    # Wraps HTTPTransport.handle_request and AsyncHTTPTransport.handle_async_request
    wrap_function_wrapper('httpx', 'HTTPTransport.handle_request', partial(...))
    wrap_function_wrapper('httpx', 'AsyncHTTPTransport.handle_async_request', partial(...))

def _uninstrument(self, **kwargs):
    unwrap(httpx.HTTPTransport, "handle_request")
    unwrap(httpx.AsyncHTTPTransport, "handle_async_request")
```

**Key Properties:**
- Uninstrumentation is symmetric - it reverses what instrument did
- State is managed cleanly (original references saved, wrapper lists cleared)
- Multiple instrument/uninstrument cycles are supported

**Test Result:**
```
Before: False
After first instrument: True
After second instrument: True  # Warning logged but no crash
After uninstrument: False
```

---

### 2. How do we detect "app calling it" vs "us calling it"?

**Answer: SOLVED ✅**

**Approach: Thread-local context flag**

```python
import threading

_coordinator_context = threading.local()
_coordinator_context.is_coordinator = False

def patched_instrument(self, *args, **kwargs):
    if getattr(_coordinator_context, 'is_coordinator', False):
        # This is us - proceed normally
        return original_instrument(self, *args, **kwargs)
    else:
        # This is the app! Time to swap
        _logger.info(f"App is taking ownership of {self.__class__.__name__}")

        # First, uninstrument our version
        if self._is_instrumented_by_opentelemetry:
            original_uninstrument(self)

        # Now let app's call proceed
        return original_instrument(self, *args, **kwargs)
```

**Why thread-local:**
- Handles concurrent instrumentor calls safely
- No global state pollution
- Works correctly in async contexts

---

### 3. What about spans created between sitecustomize and main.py?

**Answer: LOW RISK ✅**

**Analysis:**
- Between sitecustomize and main.py execution, **no HTTP requests are being handled yet**
- The application hasn't started its event loop or server
- Any spans created would already be completed before swap happens
- Swapping instrumentation doesn't affect already-completed spans

**Worst case:**
- Some internal library initialization spans might be created
- These would use our tracer provider
- They'd be exported normally
- No crashes or data loss

**Conclusion:** This is not a blocking concern.

---

### 4. What about TracerProvider initialization? ⚠️

**Answer: CRITICAL BLOCKER 🚫**

**Finding: OpenTelemetry TracerProvider can only be set ONCE**

**Code Evidence:**
```python
def _set_tracer_provider(tracer_provider: TracerProvider, log: bool) -> None:
    def set_tp() -> None:
        global _TRACER_PROVIDER
        _TRACER_PROVIDER = tracer_provider

    did_set = _TRACER_PROVIDER_SET_ONCE.do_once(set_tp)

    if log and not did_set:
        logger.warning("Overriding of current TracerProvider is not allowed")
```

**Implications:**
- If coordinator initializes a TracerProvider in sitecustomize, it's locked in
- App cannot override it later - their `set_tracer_provider()` will be ignored
- All instrumentation (ours or app's) will use the coordinator's provider

**Test Result:**
```
Current provider: <TracerProvider object at 0xffff90249f10>
Overriding of current TracerProvider is not allowed  # ← Warning logged
After set_tracer_provider: <TracerProvider object at 0xffff90249f10>  # ← Same provider!
Is same object? False  # ← App's provider object was ignored
```

**Why This Breaks the Swap Idea:**
Even if we successfully swap instrumentors, the app cannot configure their own:
- Exporter settings (OTLP endpoint, headers, protocol)
- Sampling strategy
- Resource attributes
- Span processors

---

### 5. Import-time vs call-time instrumentation

**Answer: MIXED ⚠️**

**Findings:**

**Call-time instrumentors (✅ Compatible with swap):**
- `FastAPIInstrumentor` - wraps `fastapi.FastAPI` class
- `HTTPXClientInstrumentor` - wraps HTTP transport methods
- `RequestsInstrumentor` - wraps requests library functions

These require explicit `.instrument()` call and can be uninstrumented/re-instrumented.

**Import-time side effects:**
- Some instrumentors may register hooks or modify global state on import
- However, the actual wrapping happens in `instrument()` call
- The `_is_instrumented_by_opentelemetry` flag prevents double instrumentation

**Conclusion:** Major instrumentors (FastAPI, httpx, requests) are compatible with swap mechanism.

---

## Overall Assessment

### What DOES Work ✅

1. **Instrumentor swapping** for FastAPI, httpx, requests, etc.
2. **Detection of app instrumentation calls** via patching
3. **Clean uninstrument/re-instrument cycles**
4. **Passing through app's instrumentor parameters** (hooks, excluded URLs, etc.)

### What DOESN'T Work 🚫

1. **TracerProvider swapping** - locked after first set
2. **App control over tracing backend configuration**
3. **App control over sampling or processing pipeline**

---

## Proposed Solution: Modified Hybrid Approach

### Option A: Don't Initialize Provider in Coordinator

**Approach:**
- Coordinator instruments frameworks but does NOT initialize TracerProvider
- Relies on ProxyTracerProvider or whatever the app initializes
- Swap mechanism works for instrumentors only
- App can initialize provider in main.py if they want

**Pros:**
- Swap mechanism works for instrumentors
- App retains full control over provider configuration
- No override conflict

**Cons:**
- If app doesn't initialize provider, traces go to ProxyTracerProvider (no export)
- Coordinator can't guarantee traces are exported

**Verdict:** ❌ Not acceptable - we need to ensure traces are exported

---

### Option B: Coordinator Owns Provider, Swap Only Instrumentors

**Approach:**
- Coordinator initializes TracerProvider (locked for session)
- Coordinator instruments frameworks with swap capability
- If app calls instrumentor, we swap to their version
- App's instrumentation uses coordinator's provider (cannot change it)

**Pros:**
- Guarantees traces are exported (coordinator controls backend)
- Swap works for instrumentor-level customization (hooks, excluded URLs)
- Simpler than full swap

**Cons:**
- App cannot change exporter endpoint, sampling, resource attributes
- App must accept coordinator's backend configuration

**Verdict:** ⚠️ Workable but limited

---

### Option C: Configuration-First, Swap as Safety Net

**Approach:**
1. **Default**: Coordinator initializes provider + instruments everything
2. **Config override**: Operator CR or env var declares `APP_OWNS=provider,fastapi`
   - If `provider` in list → coordinator skips provider init
   - If `fastapi` in list → coordinator skips FastAPI instrumentation
3. **Swap mechanism**: Catches cases where config is missing/wrong

**Pros:**
- Explicit control via configuration
- Swap handles edge cases and config drift
- App can own provider if declared upfront

**Cons:**
- Requires configuration awareness
- Still can't fix provider lock-in after coordinator runs

**Verdict:** ✅ **RECOMMENDED** - Best practical compromise

---

## Critical Blocker Resolution

### The Problem
Once coordinator initializes TracerProvider in sitecustomize, app cannot override backend configuration.

### The Solution
**Add configuration option to declare provider ownership BEFORE coordinator runs:**

```yaml
# In AgentObservabilityDemo CR
spec:
  runtimeCoordinator:
    instrumentationOwnership:
      tracerProvider: "app"  # Coordinator won't initialize
      fastapi: "platform"     # Coordinator instruments
      httpx: "auto"          # Swap mechanism decides
```

**Implementation:**
- Operator passes config via mounted ConfigMap
- Coordinator reads config at sitecustomize time
- If `tracerProvider: app`, coordinator skips provider initialization
- App initializes provider in main.py (runs later, no conflict)
- Swap mechanism still catches double instrumentation

---

## Final Recommendation

**PROCEED with modified hybrid approach (Option C):**

1. **Build configuration layer** (fast, low risk)
   - Allow declaring ownership at operator level
   - Pass via ConfigMap to coordinator

2. **Build swap mechanism for instrumentors** (harder, but valuable)
   - Patch FastAPI, httpx, requests instrumentors
   - Detect app calls and swap
   - Only swap instrumentors, NOT provider

3. **Document provider limitation**
   - If app needs custom backend config, must declare `tracerProvider: app`
   - Coordinator will skip provider init
   - App must initialize in main.py

**This gives us:**
- ✅ Zero-config works (coordinator handles everything)
- ✅ Full app control available (via configuration)
- ✅ Swap catches config drift
- ✅ No double instrumentation
- ❌ Cannot swap provider after coordinator inits it (documented limitation)

**Bottom line:** The swap idea works for instrumentors but NOT for TracerProvider. The hybrid approach with configuration solves this.
