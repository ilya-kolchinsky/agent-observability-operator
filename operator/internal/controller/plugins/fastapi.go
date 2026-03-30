package plugins

import (
	"github.com/example/agent-observability-operator/operator/internal/controller/plugins/common"
)

// FastAPIPlugin implements InstrumentationPlugin for FastAPI framework.
//
// FastAPI supports auto-detection: the runtime coordinator can observe app
// instrumentation calls and detect FastAPI instantiation to determine ownership.
type FastAPIPlugin struct{}

func (p *FastAPIPlugin) Name() string {
	return "fastapi"
}

func (p *FastAPIPlugin) SupportsAutoDetection() bool {
	return true
}

// ============ Type Checking ============

func (p *FastAPIPlugin) IsTrue(value interface{}) bool {
	return common.IsInterfaceTrue(value)
}

func (p *FastAPIPlugin) IsFalse(value interface{}) bool {
	return common.IsInterfaceFalse(value)
}

func (p *FastAPIPlugin) IsAuto(value interface{}) bool {
	return common.IsInterfaceAuto(value)
}

// ============ Field Resolution ============

func (p *FastAPIPlugin) ResolveField(value interface{}, defaultBool bool) interface{} {
	return common.ResolveInterfaceField(value, defaultBool)
}

func (p *FastAPIPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

func (p *FastAPIPlugin) Validate(value interface{}) error {
	// FastAPI supports auto-detection, so "auto" is valid
	return nil
}
