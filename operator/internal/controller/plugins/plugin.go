package plugins

// InstrumentationPlugin defines the interface for library-specific instrumentation logic.
//
// Each plugin encapsulates all operator-side logic for one instrumentation target:
// - Config validation (checking for unsupported values like "auto" for some libraries)
// - Type checking (is config value true, false, or "auto"?)
// - Field resolution (applying defaults when config is nil)
// - Value conversion (interface{} to string for ConfigMap serialization)
//
// Plugins enable modular extension: adding a new library requires implementing this
// interface and registering the plugin, without modifying core controller code.
type InstrumentationPlugin interface {
	// ============ Metadata ============

	// Name returns the library name (e.g., "httpx", "openai", "langchain").
	// This name must match the config field in InstrumentationSpec and the
	// key used in the runtime coordinator ConfigMap.
	Name() string

	// SupportsAutoDetection returns whether this plugin supports "auto" config value.
	// Libraries that don't support auto-detection (e.g., LangChain, MCP) must
	// return false and implement Validate() to reject "auto" values.
	SupportsAutoDetection() bool

	// ============ Config Type Checking ============

	// IsTrue checks if config value is boolean true.
	// Handles both *bool and direct bool types.
	IsTrue(value interface{}) bool

	// IsFalse checks if config value is boolean false.
	// Handles both *bool and direct bool types.
	IsFalse(value interface{}) bool

	// IsAuto checks if config value is string "auto".
	IsAuto(value interface{}) bool

	// ============ Config Resolution ============

	// ResolveField applies defaults to field value.
	//
	// Parameters:
	//   value: user-provided value (nil, true, false, or "auto")
	//   defaultBool: default value when nil (based on enableInstrumentation)
	//
	// Returns:
	//   Resolved value (bool pointer or "auto" string)
	//
	// Resolution logic:
	//   nil → &defaultBool
	//   true → &true
	//   false → &false
	//   "auto" → "auto" (if supported), otherwise error
	ResolveField(value interface{}, defaultBool bool) interface{}

	// ValueToString converts config value to string for ConfigMap serialization.
	// Conversion rules:
	//   *bool true → "true"
	//   *bool false → "false"
	//   "auto" string → "auto"
	//   nil → "" (empty, will use ConfigMap default)
	ValueToString(value interface{}) string

	// ============ Validation (optional) ============

	// Validate performs plugin-specific validation.
	// Returns error if configuration is invalid, nil otherwise.
	//
	// Common validation checks:
	//   - Reject "auto" if SupportsAutoDetection() returns false
	//   - Reject contradictory combinations (e.g., enableInstrumentation:false with lib:true)
	//
	// Note: Core validation (like enableInstrumentation contradictions) is handled
	// by the controller, but plugins can add library-specific checks.
	Validate(value interface{}) error
}
