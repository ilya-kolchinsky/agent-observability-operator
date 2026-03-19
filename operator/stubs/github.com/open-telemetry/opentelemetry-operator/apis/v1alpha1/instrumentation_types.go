package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// InstrumentationSpec captures the subset of the official OpenTelemetry Operator
// Instrumentation API used by this repository.
type InstrumentationSpec struct {
	Exporter Exporter `json:"exporter,omitempty"`
	Python   Python   `json:"python,omitempty"`
}

// Exporter configures telemetry export settings.
type Exporter struct {
	Endpoint string `json:"endpoint,omitempty"`
}

// Python configures Python auto-instrumentation settings.
type Python struct {
	Image string `json:"image,omitempty"`
}

// Instrumentation represents the OpenTelemetry Operator Instrumentation resource.
type Instrumentation struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec InstrumentationSpec `json:"spec,omitempty"`
}

// DeepCopyObject implements runtime.Object.
func (in *Instrumentation) DeepCopyObject() runtime.Object {
	if in == nil {
		return nil
	}
	out := *in
	if in.Labels != nil {
		out.Labels = make(map[string]string, len(in.Labels))
		for k, v := range in.Labels {
			out.Labels[k] = v
		}
	}
	return &out
}

// InstrumentationList contains a list of Instrumentation resources.
type InstrumentationList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Instrumentation `json:"items"`
}

// DeepCopyObject implements runtime.Object.
func (in *InstrumentationList) DeepCopyObject() runtime.Object {
	if in == nil {
		return nil
	}
	out := *in
	if in.Items != nil {
		out.Items = make([]Instrumentation, len(in.Items))
		copy(out.Items, in.Items)
	}
	return &out
}

func init() {
	SchemeBuilder.Register(&Instrumentation{}, &InstrumentationList{})
}
