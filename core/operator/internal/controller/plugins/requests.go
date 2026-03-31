package plugins

import (
	"github.com/example/agent-observability-operator/operator/internal/controller/plugins/common"
)

// RequestsPlugin implements InstrumentationPlugin for requests library.
//
// requests supports auto-detection: the runtime coordinator can observe app
// instrumentation calls and detect first requests usage to determine ownership.
type RequestsPlugin struct{}

func (p *RequestsPlugin) Name() string {
	return "requests"
}

func (p *RequestsPlugin) SupportsAutoDetection() bool {
	return true
}

// ============ Type Checking ============

func (p *RequestsPlugin) IsTrue(value interface{}) bool {
	return common.IsInterfaceTrue(value)
}

func (p *RequestsPlugin) IsFalse(value interface{}) bool {
	return common.IsInterfaceFalse(value)
}

func (p *RequestsPlugin) IsAuto(value interface{}) bool {
	return common.IsInterfaceAuto(value)
}

// ============ Field Resolution ============

func (p *RequestsPlugin) ResolveField(value interface{}, defaultBool bool) interface{} {
	return common.ResolveInterfaceField(value, defaultBool)
}

func (p *RequestsPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

func (p *RequestsPlugin) Validate(value interface{}) error {
	// requests supports auto-detection, so "auto" is valid
	return nil
}
