package plugins

import (
	"fmt"

	"github.com/example/agent-observability-operator/operator/internal/controller/plugins/common"
)

// LangChainPlugin implements InstrumentationPlugin for LangChain.
//
// LangChain does NOT support auto-detection because the official OTel instrumentor
// uses an all-or-nothing approach that instruments the entire LangChain ecosystem
// at once. This makes it unsafe to use auto-detection when apps may partially
// instrument LangChain components.
type LangChainPlugin struct{}

func (p *LangChainPlugin) Name() string {
	return "langchain"
}

func (p *LangChainPlugin) SupportsAutoDetection() bool {
	return false
}

// ============ Type Checking ============

func (p *LangChainPlugin) IsTrue(value interface{}) bool {
	return common.IsInterfaceTrue(value)
}

func (p *LangChainPlugin) IsFalse(value interface{}) bool {
	return common.IsInterfaceFalse(value)
}

func (p *LangChainPlugin) IsAuto(value interface{}) bool {
	return common.IsInterfaceAuto(value)
}

// ============ Field Resolution ============

func (p *LangChainPlugin) ResolveField(value interface{}, defaultBool bool) interface{} {
	return common.ResolveInterfaceField(value, defaultBool)
}

func (p *LangChainPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

func (p *LangChainPlugin) Validate(value interface{}) error {
	if p.IsAuto(value) {
		return fmt.Errorf(
			"langchain: auto is not supported. "+
				"The LangChain instrumentation library does not support fine-grained selective instrumentation, "+
				"which prevents safe auto-detection when apps partially instrument LangChain components. "+
				"Use langchain: true (platform instruments everything) or langchain: false (if your app instruments any LangChain components, even partially)",
		)
	}
	return nil
}
