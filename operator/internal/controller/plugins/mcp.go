package plugins

import (
	"fmt"

	"github.com/example/agent-observability-operator/operator/internal/controller/plugins/common"
)

// MCPPlugin implements InstrumentationPlugin for MCP (Model Context Protocol).
//
// MCP does NOT support auto-detection because it uses custom boundary tracing
// (not a standard OTel instrumentor). There's no instrumentor API to wrap,
// so there are no ownership signals to detect.
type MCPPlugin struct{}

func (p *MCPPlugin) Name() string {
	return "mcp"
}

func (p *MCPPlugin) SupportsAutoDetection() bool {
	return false
}

// ============ Type Checking ============

func (p *MCPPlugin) IsTrue(value interface{}) bool {
	return common.IsInterfaceTrue(value)
}

func (p *MCPPlugin) IsFalse(value interface{}) bool {
	return common.IsInterfaceFalse(value)
}

func (p *MCPPlugin) IsAuto(value interface{}) bool {
	return common.IsInterfaceAuto(value)
}

// ============ Field Resolution ============

func (p *MCPPlugin) ResolveField(value interface{}, defaultBool bool) interface{} {
	return common.ResolveInterfaceField(value, defaultBool)
}

func (p *MCPPlugin) ValueToString(value interface{}) string {
	return common.InterfaceToString(value)
}

// ============ Validation ============

func (p *MCPPlugin) Validate(value interface{}) error {
	if p.IsAuto(value) {
		return fmt.Errorf(
			"mcp: auto is not supported. "+
				"MCP instrumentation uses custom boundary tracing (not a standard OTel instrumentor), "+
				"so there are no ownership signals to detect. "+
				"Use mcp: true (platform instruments MCP boundaries) or mcp: false (if your app handles MCP tracing)",
		)
	}
	return nil
}
