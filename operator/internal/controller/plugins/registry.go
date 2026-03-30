package plugins

// Plugin registry for operator controller.
//
// This module maintains the explicit list of all instrumentation plugins
// that should be loaded by the operator. Plugins are registered here to
// enable modular extension without auto-discovery.
//
// To add a new plugin:
// 1. Implement the InstrumentationPlugin interface (create newplugin.go)
// 2. Add an instance to InstrumentationPlugins slice
// 3. Run scripts/generate-plugin-fields.sh to update generated code

// InstrumentationPlugins is the explicit registry of all plugins.
// Order matters for generation - fields will appear in this order in generated code.
var InstrumentationPlugins = []InstrumentationPlugin{
	&FastAPIPlugin{},
	&HTTPXPlugin{},
	&RequestsPlugin{},
	&LangChainPlugin{},
	&MCPPlugin{},
}

// GetPlugin returns a plugin by name.
// Returns nil if no plugin with the given name is found.
func GetPlugin(name string) InstrumentationPlugin {
	for _, p := range InstrumentationPlugins {
		if p.Name() == name {
			return p
		}
	}
	return nil
}

// GetAutoDetectionPlugins returns all plugins that support auto-detection.
func GetAutoDetectionPlugins() []InstrumentationPlugin {
	var result []InstrumentationPlugin
	for _, p := range InstrumentationPlugins {
		if p.SupportsAutoDetection() {
			result = append(result, p)
		}
	}
	return result
}

// GetPluginNames returns names of all registered plugins.
func GetPluginNames() []string {
	names := make([]string, len(InstrumentationPlugins))
	for i, p := range InstrumentationPlugins {
		names[i] = p.Name()
	}
	return names
}
