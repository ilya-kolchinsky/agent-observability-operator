package common

// Common type checking and conversion helpers used by instrumentation plugins.
//
// These utilities handle the interface{} fields in InstrumentationSpec which can
// contain either *bool or string "auto" values.

// BoolPtr creates a boolean pointer from a value.
func BoolPtr(b bool) *bool {
	return &b
}

// BoolPtrValue safely dereferences a bool pointer.
// Returns false if pointer is nil.
func BoolPtrValue(ptr *bool) bool {
	if ptr == nil {
		return false
	}
	return *ptr
}

// StringPtrValue safely dereferences a string pointer.
// Returns empty string if pointer is nil.
func StringPtrValue(ptr *string) string {
	if ptr == nil {
		return ""
	}
	return *ptr
}

// IsInterfaceTrue checks if interface{} value is boolean true.
// Handles both *bool and direct bool types.
func IsInterfaceTrue(value interface{}) bool {
	if value == nil {
		return false
	}

	// Check for *bool type
	if boolPtr, ok := value.(*bool); ok {
		return boolPtr != nil && *boolPtr
	}

	// Check for direct bool type
	if boolVal, ok := value.(bool); ok {
		return boolVal
	}

	return false
}

// IsInterfaceFalse checks if interface{} value is boolean false.
// Handles both *bool and direct bool types.
func IsInterfaceFalse(value interface{}) bool {
	if value == nil {
		return false
	}

	// Check for *bool type
	if boolPtr, ok := value.(*bool); ok {
		return boolPtr != nil && !*boolPtr
	}

	// Check for direct bool type
	if boolVal, ok := value.(bool); ok {
		return !boolVal
	}

	return false
}

// IsInterfaceAuto checks if interface{} value is string "auto".
func IsInterfaceAuto(value interface{}) bool {
	if value == nil {
		return false
	}

	strVal, ok := value.(string)
	return ok && strVal == "auto"
}

// ResolveInterfaceField applies defaults to interface{} field.
// Returns *bool or "auto" string based on input value and default.
func ResolveInterfaceField(value interface{}, defaultBool bool) interface{} {
	if value == nil {
		return BoolPtr(defaultBool)
	}

	// If already a string "auto", preserve it
	if IsInterfaceAuto(value) {
		return "auto"
	}

	// If *bool, preserve it
	if boolPtr, ok := value.(*bool); ok {
		return boolPtr
	}

	// If direct bool, convert to *bool
	if boolVal, ok := value.(bool); ok {
		return BoolPtr(boolVal)
	}

	// Fallback: use default
	return BoolPtr(defaultBool)
}

// InterfaceToString converts interface{} value to string for ConfigMap.
// Conversion rules:
//   - *bool true → "true"
//   - *bool false → "false"
//   - "auto" string → "auto"
//   - nil or unknown → "false"
func InterfaceToString(value interface{}) string {
	if value == nil {
		return "false"
	}

	// Check for string "auto"
	if strVal, ok := value.(string); ok {
		if strVal == "auto" {
			return "auto"
		}
		// Unknown string - default to false
		return "false"
	}

	// Check for *bool
	if boolPtr, ok := value.(*bool); ok {
		if boolPtr == nil {
			return "false"
		}
		if *boolPtr {
			return "true"
		}
		return "false"
	}

	// Check for direct bool
	if boolVal, ok := value.(bool); ok {
		if boolVal {
			return "true"
		}
		return "false"
	}

	// Unknown type - default to false
	return "false"
}

// InterfaceToBool converts interface{} value to bool for test comparison.
// Handles *bool and direct bool, returns false for "auto" or nil.
func InterfaceToBool(value interface{}) bool {
	if value == nil {
		return false
	}

	if boolPtr, ok := value.(*bool); ok {
		if boolPtr == nil {
			return false
		}
		return *boolPtr
	}

	if boolVal, ok := value.(bool); ok {
		return boolVal
	}

	// For "auto" string or other non-bool values, return false
	return false
}
