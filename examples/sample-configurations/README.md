# Sample Configurations

This directory contains example `AgentObservabilityDemo` custom resources demonstrating different configuration patterns.

## Available Samples

### agentobservability-sample.yaml

Contains three complete CR examples:

1. **no-existing** - Platform owns everything (full auto-instrumentation)
2. **partial-existing** - Auto-detection with selective app ownership
3. **full-existing** - App owns everything (minimal platform instrumentation)

These samples are used in the [end-to-end demo](../end-to-end-demo/).

## Sample Breakdown

### Sample 1: Platform Owns Everything

**Use case:** Greenfield app with no tracing, platform provides full observability

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: no-existing
  namespace: demo-apps
spec:
  target:
    workloadName: agent-no-existing
    containerName: app
  instrumentation:
    enableInstrumentation: true
    tracerProvider: platform
    fastapi: true
    httpx: true
    requests: true
    langchain: true
    mcp: true
    openai: true
```

**Result:**
- Platform initializes TracerProvider
- Platform instruments all available libraries
- App requires zero tracing code
- Complete observability out of the box

**When to use:**
- New applications with no tracing
- Rapid prototyping
- Development environments
- Applications that delegate all observability to platform

### Sample 2: Auto-Detection with Selective Ownership

**Use case:** Platform auto-detects ownership for most libraries, app explicitly owns some

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: partial-existing
  namespace: demo-apps
spec:
  target:
    workloadName: agent-partial-existing
    containerName: app
  instrumentation:
    autoDetection: true
    langchain: false  # App owns LangChain explicitly
    mcp: true         # Platform handles MCP (no auto-detection support)
```

**Result:**
- FastAPI, httpx, requests, OpenAI → `"auto"` (runtime detection)
- Platform waits to see if app instruments these libraries first
- LangChain → explicitly app-owned (app instruments in main.py)
- MCP → explicitly platform-owned (platform instruments)
- TracerProvider → inferred based on app behavior

**When to use:**
- Apps undergoing migration to platform observability
- Development where instrumentation ownership changes frequently
- Testing different instrumentation strategies
- Apps with mixed ownership that may evolve

**Note:** `autoDetection: true` cannot be combined with explicit values for auto-capable libraries (fastapi, httpx, requests, openai). The operator validates this and will reject contradictory configurations.

### Sample 3: App Owns Everything

**Use case:** Existing app with full tracing, platform should not interfere

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: full-existing
  namespace: demo-apps
spec:
  target:
    workloadName: agent-full-existing
    containerName: app
  instrumentation:
    enableInstrumentation: false
    tracerProvider: app
    fastapi: false
    httpx: false
    requests: false
    langchain: false
    mcp: false
    openai: false
```

**Result:**
- App initializes TracerProvider in main.py
- App instruments all libraries itself
- Platform respects app's ownership
- No duplicate spans or conflicting instrumentation

**When to use:**
- Legacy apps with existing tracing
- Apps with custom instrumentation requirements
- Production apps with stable, app-owned observability
- Apps that need precise control over instrumentation

**Note:** While `enableInstrumentation: false` disables all auto-instrumentation, the operator still patches the workload with necessary configuration (OTLP endpoint, etc.). This allows the app to send traces to the platform's collector.

## More Configuration Patterns

For additional configuration patterns and detailed explanations, see:

- [Configuration Guide](../../docs/CONFIGURATION.md) - Complete configuration reference
- [Architecture](../../docs/ARCHITECTURE.md) - Smart defaults and inference logic
- [Plugin Development](../../docs/PLUGIN_DEVELOPMENT.md) - Adding new instrumentation libraries

## Field Reference Quick Guide

### Target Fields

- `spec.target.namespace` - Target namespace (defaults to CR namespace)
- `spec.target.workloadName` - Target workload name (required)
- `spec.target.workloadKind` - Workload kind (defaults to "Deployment")
- `spec.target.containerName` - Target container name (required)

### Instrumentation Fields

**Core settings:**
- `enableInstrumentation` - Enable/disable auto-instrumentation (inferred if omitted)
- `autoDetection` - Enable runtime ownership detection (defaults to false)
- `tracerProvider` - Who initializes TracerProvider: `platform` or `app` (inferred if omitted)

**Infrastructure:**
- `customPythonImage` - Custom auto-instrumentation image
- `otelCollectorEndpoint` - OTLP collector endpoint

**Per-library (supports auto-detection):**
- `fastapi` - FastAPI instrumentation: `true`, `false`, or `"auto"`
- `httpx` - httpx instrumentation: `true`, `false`, or `"auto"`
- `requests` - requests instrumentation: `true`, `false`, or `"auto"`
- `openai` - OpenAI SDK instrumentation: `true`, `false`, or `"auto"`

**Per-library (explicit-only):**
- `langchain` - LangChain instrumentation: `true` or `false` (no `"auto"`)
- `mcp` - MCP instrumentation: `true` or `false` (no `"auto"`)

## Applying Samples

### Apply All Samples

```bash
kubectl apply -f examples/sample-configurations/agentobservability-sample.yaml
```

This creates three AgentObservabilityDemo resources in the demo-apps namespace.

### Apply Individual Samples

Extract a specific sample from the file:

```bash
# Extract the no-existing sample
kubectl apply -f - <<EOF
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: no-existing
  namespace: demo-apps
spec:
  target:
    workloadName: agent-no-existing
    containerName: app
  instrumentation:
    enableInstrumentation: true
    # ... rest of the config
EOF
```

### Verify Application

```bash
# Check CR was created
kubectl get agentobservabilitydemos -n demo-apps

# Check generated Instrumentation resource
kubectl get instrumentation -n demo-apps

# Check operator reconciled successfully
kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=100
```

## Creating Your Own Samples

### Template

```yaml
apiVersion: platform.example.com/v1alpha1
kind: AgentObservabilityDemo
metadata:
  name: my-agent
  namespace: my-namespace
spec:
  target:
    workloadName: my-deployment
    containerName: app
  instrumentation:
    # Choose your configuration pattern...

    # Option 1: Full auto-instrumentation
    enableInstrumentation: true

    # Option 2: Auto-detection
    autoDetection: true
    langchain: false  # Explicit override for non-auto lib

    # Option 3: Selective opt-out
    fastapi: false
    langchain: false
    # httpx, requests, mcp, openai → default to true

    # Option 4: Explicit control
    enableInstrumentation: true
    tracerProvider: app
    fastapi: true
    httpx: false
    # ... set all fields explicitly
```

### Validation Tips

The operator validates your configuration. Common errors:

**Error:** `enableInstrumentation is false but libraries are set to true`

**Fix:** Either enable instrumentation or remove explicit `true` values.

**Error:** `autoDetection is true but auto-capable libraries have explicit values`

**Fix:** Remove explicit values for fastapi/httpx/requests/openai when using `autoDetection: true`. You can still set explicit values for langchain/mcp since they don't support auto-detection.

## Testing Samples

After applying a sample:

1. **Check operator reconciliation:**
   ```bash
   kubectl logs -n agent-observability-system deployment/agent-observability-operator
   ```

2. **Verify Instrumentation generated:**
   ```bash
   kubectl get instrumentation -n demo-apps
   ```

3. **Check runtime coordinator decisions:**
   ```bash
   kubectl logs -n demo-apps deployment/<workload> --tail=200 | grep detection_complete
   ```

4. **Send traffic and check traces:**
   ```bash
   # Generate traffic (requires demo apps running)
   curl http://<service>:8000/run

   # Check Jaeger (requires port-forward)
   # Open http://127.0.0.1:16686
   ```

## See Also

- [Configuration Guide](../../docs/CONFIGURATION.md) - Complete field reference and patterns
- [End-to-End Demo](../end-to-end-demo/README.md) - Full demo using these samples
- [Quick Start](../../docs/QUICKSTART.md) - Setup and run instructions
- [Troubleshooting](../../docs/TROUBLESHOOTING.md) - Common issues and fixes
