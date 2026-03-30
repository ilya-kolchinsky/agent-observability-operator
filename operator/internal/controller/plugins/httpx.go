package plugins

import (
	"github.com/example/agent-observability-operator/operator/internal/controller/plugins/common"
)

// HTTPXPlugin implements InstrumentationPlugin for httpx client library.
//
// httpx supports auto-detection: the runtime coordinator can observe app
// instrumentation calls and detect first httpx usage to determine ownership.
type HTTPXPlugin struct{}

func (p *HTTPXPlugin) Name() string {
	return "httpx"
}

func (p *HTTPXPlugin) SupportsAutoDetection() bool {
	return true
}

// ============ Type Checking ============

func (p *HTTPXPlugin) IsTrue(value interface{}) bool {
	return common.IsInterfaceTrue(value)
}

func (p *HTTPXPlugin) IsFalse(value interface{}) bool {
	return common.IsInterfaceFalse(value)
}

func (p *HTTPXPlugin) IsAuto(value interface{}) bool {
	return common.IsInterfaceAuto(value)
}

// ============ Field Resolution ============

func (p *HTTPXPlugin) ResolveField(value interface{}, defaultBool bool) interface{} {
	return common.ResolveInterfaceField(value, defaultBool)
}

func (p *HTTPXPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

func (p *HTTPXPlugin) Validate(value interface{}) error {
	// httpx supports auto-detection, so "auto" is valid
	return nil
}
