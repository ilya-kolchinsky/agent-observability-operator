package controller

import (
	"testing"

	platformv1alpha1 "github.com/example/agent-observability-operator/operator/api/v1alpha1"
)

// boolPtr is a helper to create bool pointers
func boolPtr(b bool) *bool {
	return &b
}

// stringPtr is a helper to create string pointers
func stringPtr(s string) *string {
	return &s
}

func TestValidateInstrumentationSpec(t *testing.T) {
	tests := []struct {
		name    string
		spec    platformv1alpha1.InstrumentationSpec
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid: enableInstrumentation true with libs true",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(true),
				FastAPI:               boolPtr(true),
				HTTPX:                 boolPtr(true),
			},
			wantErr: false,
		},
		{
			name: "valid: enableInstrumentation false with libs false",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
				FastAPI:               boolPtr(false),
				HTTPX:                 boolPtr(false),
			},
			wantErr: false,
		},
		{
			name: "valid: enableInstrumentation false with libs omitted",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
			},
			wantErr: false,
		},
		{
			name: "valid: enableInstrumentation false with tracerProvider app",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
				TracerProvider:        stringPtr("app"),
			},
			wantErr: false,
		},
		{
			name: "valid: all fields omitted",
			spec: platformv1alpha1.InstrumentationSpec{},
			wantErr: false,
		},
		{
			name: "invalid: enableInstrumentation false with fastapi true",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
				FastAPI:               boolPtr(true),
			},
			wantErr: true,
			errMsg:  "fastapi: true",
		},
		{
			name: "invalid: enableInstrumentation false with multiple libs true",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
				FastAPI:               boolPtr(true),
				HTTPX:                 boolPtr(true),
				LangChain:             boolPtr(true),
			},
			wantErr: true,
			errMsg:  "fastapi: true",
		},
		{
			name: "invalid: enableInstrumentation false with tracerProvider platform",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
				TracerProvider:        stringPtr("platform"),
			},
			wantErr: true,
			errMsg:  "tracerProvider is 'platform'",
		},
		{
			name: "invalid: enableInstrumentation false with both lib true and tracerProvider platform",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
				FastAPI:               boolPtr(true),
				TracerProvider:        stringPtr("platform"),
			},
			wantErr: true,
			errMsg:  "fastapi: true", // Should catch library contradiction first
		},
		{
			name: "invalid: langchain auto - not supported",
			spec: platformv1alpha1.InstrumentationSpec{
				LangChain: "auto",
			},
			wantErr: true,
			errMsg:  "langchain: auto is not supported",
		},
		{
			name: "invalid: mcp auto - not supported",
			spec: platformv1alpha1.InstrumentationSpec{
				MCP: "auto",
			},
			wantErr: true,
			errMsg:  "mcp: auto is not supported",
		},
		{
			name: "valid: fastapi auto - supported",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI: "auto",
			},
			wantErr: false,
		},
		{
			name: "valid: httpx auto - supported",
			spec: platformv1alpha1.InstrumentationSpec{
				HTTPX: "auto",
			},
			wantErr: false,
		},
		{
			name: "valid: requests auto - supported",
			spec: platformv1alpha1.InstrumentationSpec{
				Requests: "auto",
			},
			wantErr: false,
		},
		{
			name: "invalid: langchain auto with other valid settings",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(true),
				FastAPI:               "auto",
				HTTPX:                 "auto",
				LangChain:             "auto", // Should fail
				MCP:                   boolPtr(true),
			},
			wantErr: true,
			errMsg:  "langchain: auto is not supported",
		},
		{
			name: "invalid: mcp auto with other valid settings",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(true),
				FastAPI:               boolPtr(true),
				HTTPX:                 "auto",
				Requests:              "auto",
				LangChain:             boolPtr(false),
				MCP:                   "auto", // Should fail
			},
			wantErr: true,
			errMsg:  "mcp: auto is not supported",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateInstrumentationSpec(&tt.spec)
			if (err != nil) != tt.wantErr {
				t.Errorf("validateInstrumentationSpec() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err != nil && tt.errMsg != "" {
				if !containsString(err.Error(), tt.errMsg) {
					t.Errorf("validateInstrumentationSpec() error = %v, want error containing %q", err, tt.errMsg)
				}
			}
		})
	}
}

func TestInferEnableInstrumentation(t *testing.T) {
	tests := []struct {
		name string
		spec platformv1alpha1.InstrumentationSpec
		want bool
	}{
		{
			name: "explicit true",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(true),
			},
			want: true,
		},
		{
			name: "explicit false",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
			},
			want: false,
		},
		{
			name: "omitted with library field specified - infer true",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI: boolPtr(true),
			},
			want: true,
		},
		{
			name: "omitted with tracerProvider specified - infer true",
			spec: platformv1alpha1.InstrumentationSpec{
				TracerProvider: stringPtr("platform"),
			},
			want: true,
		},
		{
			name: "omitted with no fields specified - infer false",
			spec: platformv1alpha1.InstrumentationSpec{},
			want: false,
		},
		{
			name: "omitted with only image/endpoint specified - infer false",
			spec: platformv1alpha1.InstrumentationSpec{
				CustomPythonImage:     "custom-image",
				OTelCollectorEndpoint: "http://collector:4318",
			},
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := inferEnableInstrumentation(&tt.spec)
			if got != tt.want {
				t.Errorf("inferEnableInstrumentation() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestInferTracerProvider(t *testing.T) {
	tests := []struct {
		name string
		spec platformv1alpha1.InstrumentationSpec
		want string
	}{
		{
			name: "all libs true - infer platform",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI:   boolPtr(true),
				HTTPX:     boolPtr(true),
				Requests:  boolPtr(true),
				LangChain: boolPtr(true),
				MCP:       boolPtr(true),
			},
			want: "platform",
		},
		{
			name: "all libs omitted (defaults to true) - infer platform",
			spec: platformv1alpha1.InstrumentationSpec{},
			want: "platform",
		},
		{
			name: "one lib false - infer app",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI:   boolPtr(false),
				HTTPX:     boolPtr(true),
				Requests:  boolPtr(true),
				LangChain: boolPtr(true),
				MCP:       boolPtr(true),
			},
			want: "app",
		},
		{
			name: "all libs false - infer app",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI:   boolPtr(false),
				HTTPX:     boolPtr(false),
				Requests:  boolPtr(false),
				LangChain: boolPtr(false),
				MCP:       boolPtr(false),
			},
			want: "app",
		},
		{
			name: "mixed libs - infer app",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI:   boolPtr(false),
				LangChain: boolPtr(false),
			},
			want: "app",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := inferTracerProvider(&tt.spec)
			if got != tt.want {
				t.Errorf("inferTracerProvider() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestResolveInstrumentationSpec(t *testing.T) {
	tests := []struct {
		name                     string
		spec                     platformv1alpha1.InstrumentationSpec
		wantEnableInstrumentation bool
		wantTracerProvider       string
		wantFastAPI              bool
		wantHTTPX                bool
	}{
		{
			name: "explicit enableInstrumentation true - all libs default to true",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(true),
			},
			wantEnableInstrumentation: true,
			wantTracerProvider:        "platform",
			wantFastAPI:               true,
			wantHTTPX:                 true,
		},
		{
			name: "explicit enableInstrumentation false - all libs default to false",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(false),
			},
			wantEnableInstrumentation: false,
			wantTracerProvider:        "app", // All libs false means app owns it
			wantFastAPI:               false,
			wantHTTPX:                 false,
		},
		{
			name: "partial libs specified - enableInstrumentation inferred true",
			spec: platformv1alpha1.InstrumentationSpec{
				FastAPI: boolPtr(false),
			},
			wantEnableInstrumentation: true,
			wantTracerProvider:        "app", // One lib false
			wantFastAPI:               false,
			wantHTTPX:                 true, // Default for unspecified
		},
		{
			name: "no fields specified - enableInstrumentation inferred false",
			spec: platformv1alpha1.InstrumentationSpec{},
			wantEnableInstrumentation: false,
			wantTracerProvider:        "app", // All libs false means app owns it
			wantFastAPI:               false,
			wantHTTPX:                 false,
		},
		{
			name: "explicit tracerProvider overrides inference",
			spec: platformv1alpha1.InstrumentationSpec{
				EnableInstrumentation: boolPtr(true),
				TracerProvider:        stringPtr("app"), // Override
				FastAPI:               boolPtr(true),
				HTTPX:                 boolPtr(true),
			},
			wantEnableInstrumentation: true,
			wantTracerProvider:        "app", // Explicit wins
			wantFastAPI:               true,
			wantHTTPX:                 true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := resolveInstrumentationSpec(&tt.spec)

			if boolPtrValue(got.EnableInstrumentation) != tt.wantEnableInstrumentation {
				t.Errorf("resolveInstrumentationSpec() enableInstrumentation = %v, want %v",
					boolPtrValue(got.EnableInstrumentation), tt.wantEnableInstrumentation)
			}
			if stringPtrValue(got.TracerProvider) != tt.wantTracerProvider {
				t.Errorf("resolveInstrumentationSpec() tracerProvider = %v, want %v",
					stringPtrValue(got.TracerProvider), tt.wantTracerProvider)
			}
			if interfaceToBool(got.FastAPI) != tt.wantFastAPI {
				t.Errorf("resolveInstrumentationSpec() fastapi = %v, want %v",
					interfaceToBool(got.FastAPI), tt.wantFastAPI)
			}
			if interfaceToBool(got.HTTPX) != tt.wantHTTPX {
				t.Errorf("resolveInstrumentationSpec() httpx = %v, want %v",
					interfaceToBool(got.HTTPX), tt.wantHTTPX)
			}
		})
	}
}

func TestResolveInstrumentationSpecWithAutoDetection(t *testing.T) {
	tests := []struct {
		name                     string
		spec                     platformv1alpha1.InstrumentationSpec
		wantEnableInstrumentation bool
		wantFastAPI              interface{} // Can be bool or "auto"
		wantHTTPX                interface{}
		wantLangChain            interface{}
		wantMCP                  interface{}
	}{
		{
			name: "autoDetection true - auto-capable libs get auto",
			spec: platformv1alpha1.InstrumentationSpec{
				AutoDetection: boolPtr(true),
			},
			wantEnableInstrumentation: true,
			wantFastAPI:               "auto", // Auto-capable
			wantHTTPX:                 "auto", // Auto-capable
			wantLangChain:             boolPtr(true), // Not auto-capable, uses enableInstrumentation default
			wantMCP:                   boolPtr(true), // Not auto-capable, uses enableInstrumentation default
		},
		{
			name: "autoDetection true with explicit overrides",
			spec: platformv1alpha1.InstrumentationSpec{
				AutoDetection: boolPtr(true),
				FastAPI:       boolPtr(false), // Explicit override
				LangChain:     boolPtr(false), // Explicit override
			},
			wantEnableInstrumentation: true,
			wantFastAPI:               boolPtr(false), // Explicit wins
			wantHTTPX:                 "auto",         // Auto from autoDetection
			wantLangChain:             boolPtr(false), // Explicit wins
			wantMCP:                   boolPtr(true),  // Not auto-capable, uses default
		},
		{
			name: "autoDetection false - normal defaults apply",
			spec: platformv1alpha1.InstrumentationSpec{
				AutoDetection:         boolPtr(false),
				EnableInstrumentation: boolPtr(true),
			},
			wantEnableInstrumentation: true,
			wantFastAPI:               boolPtr(true), // Normal default
			wantHTTPX:                 boolPtr(true), // Normal default
			wantLangChain:             boolPtr(true),
			wantMCP:                   boolPtr(true),
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := resolveInstrumentationSpec(&tt.spec)

			if boolPtrValue(got.EnableInstrumentation) != tt.wantEnableInstrumentation {
				t.Errorf("resolveInstrumentationSpec() enableInstrumentation = %v, want %v",
					boolPtrValue(got.EnableInstrumentation), tt.wantEnableInstrumentation)
			}

			// Check FastAPI
			if !interfaceEqual(got.FastAPI, tt.wantFastAPI) {
				t.Errorf("resolveInstrumentationSpec() fastapi = %v, want %v",
					got.FastAPI, tt.wantFastAPI)
			}

			// Check HTTPX
			if !interfaceEqual(got.HTTPX, tt.wantHTTPX) {
				t.Errorf("resolveInstrumentationSpec() httpx = %v, want %v",
					got.HTTPX, tt.wantHTTPX)
			}

			// Check LangChain
			if !interfaceEqual(got.LangChain, tt.wantLangChain) {
				t.Errorf("resolveInstrumentationSpec() langchain = %v, want %v",
					got.LangChain, tt.wantLangChain)
			}

			// Check MCP
			if !interfaceEqual(got.MCP, tt.wantMCP) {
				t.Errorf("resolveInstrumentationSpec() mcp = %v, want %v",
					got.MCP, tt.wantMCP)
			}
		})
	}
}

// interfaceEqual compares two interface{} values considering bool pointers and strings
func interfaceEqual(a, b interface{}) bool {
	// Handle string comparison
	aStr, aIsStr := a.(string)
	bStr, bIsStr := b.(string)
	if aIsStr && bIsStr {
		return aStr == bStr
	}
	if aIsStr != bIsStr {
		return false
	}

	// Handle bool pointer comparison
	aBool, aIsBoolPtr := a.(*bool)
	bBool, bIsBoolPtr := b.(*bool)
	if aIsBoolPtr && bIsBoolPtr {
		if aBool == nil && bBool == nil {
			return true
		}
		if aBool == nil || bBool == nil {
			return false
		}
		return *aBool == *bBool
	}

	// Fallback to direct comparison
	return a == b
}

// Helper function to check if a string contains a substring
func containsString(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && (s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || containsSubstring(s, substr)))
}

func containsSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// Helper function to convert interface{} field to bool for testing
// Handles both *bool and "auto" string values
func interfaceToBool(value interface{}) bool {
	if value == nil {
		return false
	}
	if boolPtr, ok := value.(*bool); ok {
		if boolPtr == nil {
			return false
		}
		return *boolPtr
	}
	// For "auto" string or other non-bool values, return false for test comparison
	return false
}
