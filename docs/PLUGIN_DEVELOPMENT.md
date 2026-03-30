# Plugin Development Guide

This guide explains how to add a new instrumentation library plugin to the agent observability operator.

## Overview

The operator uses a plugin architecture to support different instrumentation libraries. Each plugin encapsulates library-specific logic for:
- **Go side (Operator)**: Config validation, type checking, field resolution
- **Python side (Runtime Coordinator)**: Detection, instrumentation, auto-detection (optional)

## Adding a New Plugin

### Step 1: Implement the Python Plugin

Create a new file in `runtime-coordinator/agent_obs_runtime/plugins/` (e.g., `openai.py`):

```python
"""OpenAI SDK instrumentation plugin."""

import logging
from .base import InstrumentationPlugin
from .common.detection_utils import is_library_available, is_library_instrumented
from .common.ownership import OwnershipState

LOGGER = logging.getLogger(__name__)


class OpenAIPlugin(InstrumentationPlugin):
    """OpenAI SDK instrumentation plugin with auto-detection support."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def supports_auto_detection(self) -> bool:
        return True  # Set to False if auto-detection not supported

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true (not 'auto')."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return OpenAI instrumentation dependencies."""
        return ["opentelemetry-instrumentation-openai-v2>=0.1.0"]

    def instrument(self):
        """Instrument OpenAI using official OTel instrumentor."""
        try:
            from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

            OpenAIInstrumentor().instrument()
            LOGGER.info("Instrumented OpenAI")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument OpenAI: {exc}")
            raise

    # Optional: implement these only if supports_auto_detection=True
    def detect_ownership(self) -> OwnershipState:
        """Detect if app has already instrumented OpenAI."""
        if not is_library_available("openai"):
            return OwnershipState.UNDECIDED

        if is_library_instrumented("opentelemetry.instrumentation.openai_v2"):
            LOGGER.debug("OpenAI already instrumented (app owns)")
            return OwnershipState.APP

        return OwnershipState.UNDECIDED

    def install_ownership_wrappers(self, resolver):
        """Install two-wrapper approach for OpenAI auto-detection."""
        # Implement instrumentor API wrapper + first-use detection
        # See httpx.py for a complete example
        pass
```

**Key decisions:**
- `supports_auto_detection`: Set to `True` if you can detect app ownership at runtime
- `has_otel_instrumentor`: Set to `False` if using custom instrumentation (like MCP)
- `dependencies()`: Return list of pip packages required for instrumentation. These are automatically added to `custom-python-image/requirements.txt` during build. Return empty list `[]` if no external packages are needed (e.g., MCP uses only base OTel packages)

### Step 2: Implement the Go Plugin

Create a new file in `operator/internal/controller/plugins/` (e.g., `openai.go`):

```go
package plugins

import (
	"github.com/example/agent-observability-operator/operator/internal/controller/plugins/common"
)

// OpenAIPlugin implements InstrumentationPlugin for OpenAI SDK.
type OpenAIPlugin struct{}

func (p *OpenAIPlugin) Name() string {
	return "openai"
}

func (p *OpenAIPlugin) SupportsAutoDetection() bool {
	return true
}

// ============ Type Checking ============

func (p *OpenAIPlugin) IsTrue(value interface{}) bool {
	return common.IsInterfaceTrue(value)
}

func (p *OpenAIPlugin) IsFalse(value interface{}) bool {
	return common.IsInterfaceFalse(value)
}

func (p *OpenAIPlugin) IsAuto(value interface{}) bool {
	return common.IsInterfaceAuto(value)
}

// ============ Field Resolution ============

func (p *OpenAIPlugin) ResolveField(value interface{}, defaultBool bool) interface{} {
	return common.ResolveInterfaceField(value, defaultBool)
}

func (p *OpenAIPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

func (p *OpenAIPlugin) Validate(value interface{}) error {
	// OpenAI supports auto-detection, so "auto" is valid
	// Add custom validation if needed (e.g., reject "auto" like LangChain/MCP)
	return nil
}
```

**Key decisions:**
- `SupportsAutoDetection()`: Must match Python plugin's `supports_auto_detection`
- `Validate()`: Add library-specific validation (e.g., reject "auto" if not supported)

### Step 3: Register the Plugins

**Python registry** (`runtime-coordinator/agent_obs_runtime/plugins/registry.py`):

```python
from .openai import OpenAIPlugin  # Add import

INSTRUMENTATION_PLUGINS: list[InstrumentationPlugin] = [
    FastAPIPlugin(),
    HTTPXPlugin(),
    RequestsPlugin(),
    LangChainPlugin(),
    MCPPlugin(),
    OpenAIPlugin(),  # Add plugin
]
```

**Go registry** (`operator/internal/controller/plugins/registry.go`):

```go
var InstrumentationPlugins = []InstrumentationPlugin{
	&FastAPIPlugin{},
	&HTTPXPlugin{},
	&RequestsPlugin{},
	&LangChainPlugin{},
	&MCPPlugin{},
	&OpenAIPlugin{},  // Add plugin
}
```

### Step 4: Add Field to CRD Types

Add the plugin field to `operator/api/v1alpha1/agentobservability_types.go`:

```go
// InstrumentationSpec configures instrumentation behavior.
type InstrumentationSpec struct {
	// ... existing fields ...

	// OpenAI enables openai instrumentation.
	// Can be: true (platform), false (app), "auto" (runtime detection), or omitted (defaults to EnableInstrumentation)
	// Generated field - managed by plugin system
	OpenAI interface{} `json:"openai,omitempty"`
}
```

### Step 5: Update Helper Functions

Add the new plugin to `operator/internal/controller/agentobservability_controller.go`:

In `getPluginFieldValue()`:
```go
func getPluginFieldValue(spec *platformv1alpha1.InstrumentationSpec, pluginName string) interface{} {
	switch pluginName {
	case "fastapi":
		return spec.FastAPI
	case "httpx":
		return spec.HTTPX
	case "requests":
		return spec.Requests
	case "langchain":
		return spec.LangChain
	case "mcp":
		return spec.MCP
	case "openai":  // Add case
		return spec.OpenAI
	default:
		return nil
	}
}
```

In `setPluginFieldValue()`:
```go
func setPluginFieldValue(spec *platformv1alpha1.InstrumentationSpec, pluginName string, value interface{}) {
	switch pluginName {
	// ... existing cases ...
	case "openai":  // Add case
		spec.OpenAI = value
	}
}
```

### Step 6: Regenerate Artifacts

Run the generation scripts to update CRD and requirements.txt:

```bash
# Update CRD YAML with new plugin field
scripts/generate-plugin-fields.sh

# Update requirements.txt with plugin dependencies
python scripts/generate-requirements.py
```

This updates:
- `manifests/crd/agentobservability-crd.yaml` with the new plugin field
- `custom-python-image/requirements.txt` with plugin dependencies

Note: `generate-requirements.py` is automatically run during `make build-images`, but you can run it manually to preview the updated requirements.

### Step 7: Test Your Plugin

**Python tests** (`runtime-coordinator/tests/plugins/test_openai.py`):

```python
import unittest
from agent_obs_runtime.plugins.openai import OpenAIPlugin


class TestOpenAIPlugin(unittest.TestCase):
    def test_plugin_name(self):
        plugin = OpenAIPlugin()
        self.assertEqual(plugin.name, "openai")

    def test_should_instrument_with_true(self):
        plugin = OpenAIPlugin()
        self.assertTrue(plugin.should_instrument(True))

    def test_should_instrument_with_auto(self):
        plugin = OpenAIPlugin()
        self.assertFalse(plugin.should_instrument("auto"))

    def test_should_instrument_with_false(self):
        plugin = OpenAIPlugin()
        self.assertFalse(plugin.should_instrument(False))
```

**Go tests** (`operator/internal/controller/plugins/openai_test.go`):

```go
package plugins

import (
	"testing"
)

func TestOpenAIPlugin_Name(t *testing.T) {
	plugin := &OpenAIPlugin{}
	if plugin.Name() != "openai" {
		t.Errorf("expected name 'openai', got '%s'", plugin.Name())
	}
}

func TestOpenAIPlugin_SupportsAutoDetection(t *testing.T) {
	plugin := &OpenAIPlugin{}
	if !plugin.SupportsAutoDetection() {
		t.Error("expected OpenAI to support auto-detection")
	}
}
```

## Auto-Detection Pattern

If your plugin supports auto-detection, implement the **two-wrapper approach**:

1. **Instrumentor API Wrapper**: Wraps `YourInstrumentor.instrument()` to observe app ownership claims
2. **First-Use Wrapper**: Wraps library entry points to detect first use for platform claims

See `httpx.py` for a complete reference implementation.

## Libraries That Don't Support Auto-Detection

Some libraries cannot support auto-detection:

- **All-or-nothing instrumentation** (LangChain): The instrumentor instruments the entire ecosystem at once, making partial detection unsafe
- **Custom instrumentation without standard OTel instrumentor** (MCP): No instrumentor API to wrap for ownership signals

For these libraries:
- Set `supports_auto_detection=False`
- Set `SupportsAutoDetection()=false`
- Implement validation to reject "auto" config values

## Common Utilities

### Python

Located in `runtime-coordinator/agent_obs_runtime/plugins/common/`:

- `ownership.py`: OwnershipResolver state machine (UNDECIDED → PLATFORM/APP)
- `wrapper_utils.py`: Thread-local coordinator context, diagnostics emission
- `detection_utils.py`: Library availability checks, instrumentation detection

### Go

Located in `operator/internal/controller/plugins/common/`:

- `helpers.go`: Type checking, conversion utilities for interface{} fields

## Best Practices

1. **Name consistency**: Use lowercase plugin names matching the library package name
2. **Error handling**: Log warnings on instrumentation failure, raise exceptions
3. **Validation**: Reject unsupported configurations early (in Go Validate())
4. **Documentation**: Add clear comments explaining auto-detection support decisions
5. **Testing**: Cover all config value types (true, false, "auto", nil)
6. **Thread safety**: Use thread-local context for coordinator vs app detection
7. **Cleanup**: Remove wrappers after ownership resolution to avoid overhead

## Troubleshooting

**Import errors in Python**: Ensure `__init__.py` exists in `plugins/` and `plugins/common/`

**Field not found in Go**: Run `scripts/generate-plugin-fields.sh` to update CRD

**Auto-detection not working**: Check ownership wrappers are only installed when config value is "auto"

**Validation errors**: Ensure Go plugin's `Validate()` and Python plugin's validation logic match

**Tests failing**: Verify plugin is registered in both Python and Go registries

## Reference Implementations

- **Full auto-detection**: `httpx.py`, `httpx.go`
- **Simple explicit-only**: `langchain.py`, `langchain.go` (rejects "auto")
- **Custom instrumentation**: `mcp.py`, `mcp.go` (no OTel instrumentor)
