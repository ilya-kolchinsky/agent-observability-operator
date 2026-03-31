package v1alpha1

import metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

// AgentObservabilityDemoSpec defines the desired state of AgentObservabilityDemo.
type AgentObservabilityDemoSpec struct {
	Target          TargetSpec          `json:"target"`
	Instrumentation InstrumentationSpec `json:"instrumentation"`
}

// TargetSpec identifies the workload and container that the operator should prepare.
type TargetSpec struct {
	Namespace     string `json:"namespace,omitempty"`
	WorkloadName  string `json:"workloadName,omitempty"`
	WorkloadKind  string `json:"workloadKind,omitempty"`
	ContainerName string `json:"containerName,omitempty"`
}

// InstrumentationSpec configures instrumentation behavior.
type InstrumentationSpec struct {
	// CustomPythonImage specifies the custom Python auto-instrumentation image
	CustomPythonImage string `json:"customPythonImage,omitempty"`

	// OTelCollectorEndpoint specifies the OpenTelemetry collector endpoint
	OTelCollectorEndpoint string `json:"otelCollectorEndpoint,omitempty"`

	// EnableInstrumentation controls whether auto-instrumentation is enabled.
	// If true, auto-instrumentation is enabled with library defaults.
	// If false, auto-instrumentation is disabled regardless of other settings.
	// If omitted and other instrumentation fields are specified, defaults to true.
	// If omitted and no other instrumentation fields are specified, defaults to false.
	EnableInstrumentation *bool `json:"enableInstrumentation,omitempty"`

	// TracerProvider specifies who owns TracerProvider initialization ("platform" or "app").
	// If omitted, inferred from library field values:
	// - All library fields true (or default) → "platform"
	// - At least one library field false → "app"
	TracerProvider *string `json:"tracerProvider,omitempty"`

	// AutoDetection enables automatic ownership detection for all supported libraries.
	// When true, libraries that support auto-detection (FastAPI, HTTPX, Requests, OpenAI)
	// default to "auto" instead of the enableInstrumentation value.
	// Libraries without auto-detection support (LangChain, MCP) fall back to enableInstrumentation.
	// Individual library fields can still override this behavior.
	// Default: false (explicit configuration required)
	AutoDetection *bool `json:"autoDetection,omitempty"`

	// FastAPI enables fastapi instrumentation.
	// Can be: true (platform), false (app), "auto" (runtime detection), or omitted (defaults to EnableInstrumentation)
	// Generated field - see operator/api/v1alpha1/agentobservability_types_generated.go
	FastAPI interface{} `json:"fastapi,omitempty"`

	// HTTPX enables httpx instrumentation.
	// Can be: true (platform), false (app), "auto" (runtime detection), or omitted (defaults to EnableInstrumentation)
	// Generated field - see operator/api/v1alpha1/agentobservability_types_generated.go
	HTTPX interface{} `json:"httpx,omitempty"`

	// Requests enables requests instrumentation.
	// Can be: true (platform), false (app), "auto" (runtime detection), or omitted (defaults to EnableInstrumentation)
	// Generated field - see operator/api/v1alpha1/agentobservability_types_generated.go
	Requests interface{} `json:"requests,omitempty"`

	// LangChain enables langchain instrumentation.
	// Can be: true (platform), false (app), or omitted (defaults to EnableInstrumentation)
	// Note: "auto" is NOT supported - validation will reject it
	// Generated field - see operator/api/v1alpha1/agentobservability_types_generated.go
	LangChain interface{} `json:"langchain,omitempty"`

	// MCP enables mcp instrumentation.
	// Can be: true (platform), false (app), or omitted (defaults to EnableInstrumentation)
	// Note: "auto" is NOT supported - validation will reject it
	// Generated field - see operator/api/v1alpha1/agentobservability_types_generated.go
	MCP interface{} `json:"mcp,omitempty"`

	// OpenAI enables openai instrumentation.
	// Can be: true (platform), false (app), "auto" (runtime detection), or omitted (defaults to EnableInstrumentation)
	// Generated field - see operator/api/v1alpha1/agentobservability_types_generated.go
	OpenAI interface{} `json:"openai,omitempty"`
}

// AgentObservabilityDemoStatus defines the observed state of AgentObservabilityDemo.
type AgentObservabilityDemoStatus struct {
	Phase                        string `json:"phase,omitempty"`
	ObservedGeneration           int64  `json:"observedGeneration,omitempty"`
	GeneratedInstrumentationName string `json:"generatedInstrumentationName,omitempty"`
	GeneratedConfigMapName       string `json:"generatedConfigMapName,omitempty"`
	TargetWorkloadRef            string `json:"targetWorkloadRef,omitempty"`
	Message                      string `json:"message,omitempty"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status
//+kubebuilder:resource:path=agentobservabilitydemos,singular=agentobservabilitydemo,scope=Namespaced,shortName=aodemo
//+kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
//+kubebuilder:printcolumn:name="Target",type=string,JSONPath=`.status.targetWorkloadRef`
//+kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// AgentObservabilityDemo is the Schema for the agent observability demo API.
type AgentObservabilityDemo struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   AgentObservabilityDemoSpec   `json:"spec,omitempty"`
	Status AgentObservabilityDemoStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

// AgentObservabilityDemoList contains a list of AgentObservabilityDemo.
type AgentObservabilityDemoList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []AgentObservabilityDemo `json:"items"`
}

func init() {
	SchemeBuilder.Register(&AgentObservabilityDemo{}, &AgentObservabilityDemoList{})
}
