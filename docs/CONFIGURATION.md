# Configuration Guide

This guide explains how to configure the `AutoInstrumentation` custom resource.

## Overview

The `AutoInstrumentation` custom resource provides flexible configuration with smart defaults and inference logic. The system uses a **plugin architecture** where each instrumentation library is configured independently.

## Configuration Schema

### Target Specification

**Required fields:**
- `spec.target.workloadName` - Target workload name (required)
- `spec.target.containerName` - Target container name within the workload (required)

**Optional fields:**
- `spec.target.namespace` - Target workload namespace (defaults to CR namespace)
- `spec.target.workloadKind` - Target workload kind (defaults to "Deployment")

### Instrumentation Configuration

**Optional fields:**
- `spec.instrumentation.customPythonImage` - Custom auto-instrumentation image reference (defaults to `agent-observability/custom-python-autoinstrumentation:latest`)
- `spec.instrumentation.otelCollectorEndpoint` - OTLP endpoint for traces (defaults to `http://agent-observability-collector.observability.svc.cluster.local:4318`)
- `spec.instrumentation.enableInstrumentation` - Enable/disable auto-instrumentation (inferred if omitted)
- `spec.instrumentation.autoDetection` - Enable runtime ownership detection for auto-capable libraries (defaults to `false`)
- `spec.instrumentation.tracerProvider` - Who owns TracerProvider initialization: `platform` or `app` (inferred if omitted)

**Per-library fields:**
- `spec.instrumentation.fastapi` - FastAPI instrumentation: `true`, `false`, or `"auto"` (supports auto-detection)
- `spec.instrumentation.httpx` - httpx instrumentation: `true`, `false`, or `"auto"` (supports auto-detection)
- `spec.instrumentation.requests` - requests instrumentation: `true`, `false`, or `"auto"` (supports auto-detection)
- `spec.instrumentation.langchain` - LangChain instrumentation: `true` or `false` (explicit-only)
- `spec.instrumentation.mcp` - MCP instrumentation: `true` or `false` (explicit-only)
- `spec.instrumentation.openai` - OpenAI instrumentation: `true`, `false`, or `"auto"` (supports auto-detection)

## Smart Defaults and Inference

### enableInstrumentation Inference

The operator uses smart logic to determine whether auto-instrumentation should be enabled:

**If explicitly set:**
- That value is used directly

**If omitted and other instrumentation fields are specified:**
- Defaults to `true` (implicit opt-in)
- Example: Setting `fastapi: false` implies you want instrumentation enabled

**If omitted and no instrumentation fields are specified:**
- Defaults to `false` (production-safe default)
- Example: Empty `instrumentation: {}` means no auto-instrumentation

**If explicitly set to `false`:**
- All auto-instrumentation is disabled
- All library fields must be `false` or omitted (validation will reject contradictions)

### tracerProvider Inference

The operator infers who should initialize the TracerProvider based on library configuration:

**Infers `platform` when:**
- All library fields are `true` (or default to true)
- No library explicitly opts out

**Infers `app` when:**
- At least one library field is explicitly `false`
- Indicates app has some ownership of instrumentation

**Can be explicitly overridden:**
- Set `tracerProvider: platform` or `tracerProvider: app` to override inference

### autoDetection Behavior

When `autoDetection: true`:
- Auto-capable libraries (fastapi, httpx, requests, openai) use runtime ownership detection
- Platform defers instrumentation decisions until it can detect app ownership claims
- Explicit-only libraries (langchain, mcp) still require explicit true/false configuration
- Cannot specify explicit values for auto-capable libraries (validation will reject)

When `autoDetection: false` (default):
- All libraries use explicit true/false configuration
- No runtime ownership detection
- More predictable, but less adaptive to app changes

### Library Field Defaults

**When `enableInstrumentation` is `true`:**
- All library fields default to `true`
- Platform instruments everything unless explicitly opted out

**When `enableInstrumentation` is `false`:**
- All library fields default to `false`
- No instrumentation unless something is broken (validation prevents this)

**When `autoDetection` is `true`:**
- Auto-capable libraries default to `"auto"` (runtime detection)
- Explicit-only libraries still default to `true`

## Configuration Validation

The operator validates configuration to prevent contradictions:

### Validation Rules

1. **enableInstrumentation vs library fields:**
   - Rejects if `enableInstrumentation: false` AND any library field is explicitly `true`
   - Example: `{enableInstrumentation: false, fastapi: true}` → ERROR

2. **autoDetection vs explicit values:**
   - Rejects if `autoDetection: true` AND any auto-capable library has explicit value
   - Example: `{autoDetection: true, fastapi: false}` → ERROR
   - Reason: autoDetection means "let runtime decide", but explicit value means "platform decides now"

3. **Library-specific validation:**
   - LangChain and MCP plugins reject `"auto"` value (they don't support auto-detection)
   - Auto-capable plugins (fastapi, httpx, requests, openai) accept `"auto"`

## Configuration Patterns

### Pattern 1: Full Auto-Instrumentation (Demo/Development)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-agent
spec:
  target:
    namespace: my-namespace
    workloadName: my-deployment
    containerName: app
  instrumentation:
    enableInstrumentation: true
# All libs → true, tracerProvider → platform
```

**Result:**
- Platform initializes TracerProvider
- Platform instruments all available libraries
- Simple, batteries-included approach

### Pattern 2: Auto-Detection (Adaptive to App Changes)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-agent
spec:
  target:
    namespace: my-namespace
    workloadName: my-deployment
    containerName: app
  instrumentation:
    autoDetection: true
    langchain: false  # Explicit-only lib still needs value
# Auto-capable libs → "auto" (runtime detection)
# tracerProvider → inferred based on app behavior
```

**Result:**
- Auto-capable libraries (fastapi, httpx, requests, openai) use runtime detection
- Platform waits to see if app instruments them first
- LangChain explicitly opted out (app owns it)
- Adapts to app changes without CR updates

### Pattern 3: Selective Opt-Out (Partial Existing Instrumentation)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-agent
spec:
  target:
    namespace: my-namespace
    workloadName: my-deployment
    containerName: app
  instrumentation:
    fastapi: false      # App instruments FastAPI
    langchain: false    # App instruments LangChain
# enableInstrumentation → true (implicit)
# Other libs (httpx, requests, mcp) → true
# tracerProvider → app (inferred)
```

**Result:**
- App initializes TracerProvider (inferred from opt-outs)
- Platform instruments httpx, requests, mcp
- App instruments FastAPI and LangChain
- Mixed ownership scenario

### Pattern 4: Minimal Instrumentation (Full Existing Setup)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-agent
spec:
  target:
    namespace: my-namespace
    workloadName: my-deployment
    containerName: app
  instrumentation:
    enableInstrumentation: true
    fastapi: false
    httpx: false
    requests: false
    langchain: false
    mcp: false
# tracerProvider → app (inferred)
```

**Result:**
- App owns everything
- Platform doesn't instrument anything
- Platform still injects config/mounts (useful for future changes)

### Pattern 5: Production Safe Default (No Instrumentation)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-agent
spec:
  target:
    namespace: my-namespace
    workloadName: my-deployment
    containerName: app
  instrumentation: {}
# enableInstrumentation → false (safe default)
```

**Result:**
- No auto-instrumentation applied
- Safe for production where you haven't decided on instrumentation yet

### Pattern 6: Explicit Override (Fine-Grained Control)

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AutoInstrumentation
metadata:
  name: my-agent
spec:
  target:
    namespace: my-namespace
    workloadName: my-deployment
    containerName: app
  instrumentation:
    enableInstrumentation: true
    tracerProvider: app      # Override inference
    fastapi: true
    httpx: false
    requests: true
    langchain: false
    mcp: true
```

**Result:**
- Explicit control over every decision
- No inference or auto-detection
- Platform instruments: fastapi, requests, mcp
- App instruments: httpx, langchain
- App initializes TracerProvider (explicit override)

## Auto-Detection vs Explicit Configuration

### When to Use Auto-Detection

**Use `autoDetection: true` when:**
- App instrumentation changes frequently during development
- You want the platform to adapt without CR updates
- You trust the runtime detection heuristics
- You're okay with startup-time overhead of detection

**Example use case:**
- Development environment where app code changes often
- Testing different instrumentation setups
- Migration from app-owned to platform-owned instrumentation

### When to Use Explicit Configuration

**Use explicit `true`/`false` values when:**
- You want predictable, deterministic behavior
- You know exactly which libraries app vs platform should instrument
- You prefer compile-time decisions over runtime detection
- You want to minimize startup overhead

**Example use case:**
- Production deployments with stable instrumentation setup
- Clear ownership boundaries between app and platform
- Performance-sensitive workloads

## Configuration Troubleshooting

### Validation Error: enableInstrumentation Contradiction

**Error message:**
```
enableInstrumentation is false but the following libraries are explicitly set to true: [fastapi, httpx]
```

**Cause:**
You disabled instrumentation but also tried to enable specific libraries.

**Fix:**
Either enable instrumentation or remove the explicit `true` values:
```yaml
# Option 1: Enable instrumentation
instrumentation:
  enableInstrumentation: true
  fastapi: true

# Option 2: Disable everything
instrumentation:
  enableInstrumentation: false
```

### Validation Error: autoDetection Contradiction

**Error message:**
```
autoDetection is true but the following auto-capable libraries have explicit values: [fastapi: false]
```

**Cause:**
Auto-detection means "let runtime decide", but you also provided an explicit decision.

**Fix:**
Remove explicit values for auto-capable libraries:
```yaml
# Before (ERROR)
instrumentation:
  autoDetection: true
  fastapi: false  # Conflict!

# After (OK)
instrumentation:
  autoDetection: true
  langchain: false  # OK - langchain is explicit-only
```

### No Instrumentation Applied

**Symptoms:**
- No traces appearing in Jaeger
- Pod annotations missing

**Check:**
1. Is `enableInstrumentation` explicitly or implicitly `false`?
2. Is the CR in the correct namespace?
3. Did the operator reconcile the CR successfully?

**Debug:**
```bash
kubectl get autoinstrumentations -n <namespace> -o yaml
kubectl logs -n agent-observability-system deployment/agent-observability-operator
```

### Unexpected Coordinator Decisions

**Symptoms:**
- Coordinator instruments differently than expected
- Runtime detection not working

**Check:**
1. Are you using `autoDetection: true` or explicit values?
2. Is the app instrumentation code running before or after sitecustomize?
3. Check coordinator diagnostics in pod logs

**Debug:**
```bash
kubectl logs -n <namespace> deployment/<workload> --tail=200 | grep detection_complete
```

## Advanced Configuration

### Custom OTLP Endpoint

```yaml
instrumentation:
  otelCollectorEndpoint: http://my-collector.my-namespace.svc.cluster.local:4318
```

### Custom Python Image

```yaml
instrumentation:
  customPythonImage: my-registry.io/custom-python-autoinstrumentation:v1.2.3
```

### Target Different Workload Types

```yaml
target:
  workloadKind: StatefulSet  # Note: Only Deployment is currently supported in this PoC
  workloadName: my-statefulset
```

## See Also

- [Quick Start Guide](QUICKSTART.md) - Step-by-step setup instructions
- [Architecture](ARCHITECTURE.md) - System design and components
- [Plugin Development](PLUGIN_DEVELOPMENT.md) - Adding new instrumentation libraries
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
