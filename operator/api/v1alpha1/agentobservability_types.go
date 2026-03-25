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

	// TracerProvider specifies who owns TracerProvider initialization ("platform" or "app")
	TracerProvider string `json:"tracerProvider,omitempty"`

	// FastAPI enables FastAPI instrumentation
	FastAPI bool `json:"fastapi,omitempty"`

	// HTTPX enables httpx client instrumentation
	HTTPX bool `json:"httpx,omitempty"`

	// Requests enables requests library instrumentation
	Requests bool `json:"requests,omitempty"`

	// LangChain enables LangChain instrumentation
	LangChain bool `json:"langchain,omitempty"`

	// MCP enables MCP boundary instrumentation
	MCP bool `json:"mcp,omitempty"`
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
