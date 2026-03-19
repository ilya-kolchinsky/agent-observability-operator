package v1alpha1

import metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

// AgentObservabilityDemoSpec defines the desired state of AgentObservabilityDemo.
type AgentObservabilityDemoSpec struct {
	Target             TargetSpec             `json:"target"`
	Instrumentation    InstrumentationSpec    `json:"instrumentation"`
	RuntimeCoordinator RuntimeCoordinatorSpec `json:"runtimeCoordinator"`
	Demo               DemoSpec               `json:"demo"`
}

// TargetSpec identifies the workload and container that the operator should prepare.
type TargetSpec struct {
	Namespace     string `json:"namespace,omitempty"`
	WorkloadName  string `json:"workloadName,omitempty"`
	WorkloadKind  string `json:"workloadKind,omitempty"`
	ContainerName string `json:"containerName,omitempty"`
}

// InstrumentationSpec configures how demo instrumentation assets should be created.
type InstrumentationSpec struct {
	Enabled               bool   `json:"enabled,omitempty"`
	Language              string `json:"language,omitempty"`
	CustomPythonImage     string `json:"customPythonImage,omitempty"`
	OTelCollectorEndpoint string `json:"otelCollectorEndpoint,omitempty"`
	Mode                  string `json:"mode,omitempty"`
}

// RuntimeCoordinatorSpec configures the runtime coordinator feature set.
type RuntimeCoordinatorSpec struct {
	Enabled          bool                   `json:"enabled,omitempty"`
	DiagnosticsLevel string                 `json:"diagnosticsLevel,omitempty"`
	Heuristics       RuntimeHeuristicsSpec  `json:"heuristics"`
	Patchers         RuntimePatchersSpec    `json:"patchers"`
	Suppression      RuntimeSuppressionSpec `json:"suppression"`
}

// RuntimeHeuristicsSpec controls detection heuristics that help avoid redundant instrumentation.
type RuntimeHeuristicsSpec struct {
	DetectExistingProvider         bool `json:"detectExistingProvider,omitempty"`
	DetectSpanProcessors           bool `json:"detectSpanProcessors,omitempty"`
	DetectFrameworkInstrumentation bool `json:"detectFrameworkInstrumentation,omitempty"`
	DetectKnownVendorTracing       bool `json:"detectKnownVendorTracing,omitempty"`
}

// RuntimePatchersSpec enables patchers for specific libraries and boundaries.
type RuntimePatchersSpec struct {
	HTTPClient  bool `json:"httpClient,omitempty"`
	GRPCClient  bool `json:"grpcClient,omitempty"`
	ASGI        bool `json:"asgi,omitempty"`
	WSGI        bool `json:"wsgi,omitempty"`
	GenAIOpenAI bool `json:"genaiOpenAI,omitempty"`
	MCPBoundary bool `json:"mcpBoundary,omitempty"`
}

// RuntimeSuppressionSpec configures how duplicate instrumentation is suppressed.
type RuntimeSuppressionSpec struct {
	DisableDuplicateInstrumentations bool `json:"disableDuplicateInstrumentations,omitempty"`
}

// DemoSpec controls the optional demo application behavior.
type DemoSpec struct {
	CreateSampleWorkload bool   `json:"createSampleWorkload,omitempty"`
	SampleAppVariant     string `json:"sampleAppVariant,omitempty"`
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
