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

func (p *OpenAIPlugin) ResolveField(value interface{}, defaultValue bool) interface{} {
	return common.ResolveInterfaceField(value, defaultValue)
}

func (p *OpenAIPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

// Validate checks if the value is valid for this plugin.
// OpenAI supports auto-detection, so "auto" is allowed.
func (p *OpenAIPlugin) Validate(value interface{}) error {
	// OpenAI supports auto-detection, so no additional validation needed
	return nil
}
