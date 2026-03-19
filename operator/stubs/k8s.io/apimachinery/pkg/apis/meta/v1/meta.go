package v1

import (
	"time"

	"k8s.io/apimachinery/pkg/runtime"
)

type TypeMeta struct {
	Kind       string `json:"kind,omitempty"`
	APIVersion string `json:"apiVersion,omitempty"`
}

type ObjectMeta struct {
	Name              string            `json:"name,omitempty"`
	Namespace         string            `json:"namespace,omitempty"`
	Generation        int64             `json:"generation,omitempty"`
	Labels            map[string]string `json:"labels,omitempty"`
	CreationTimestamp Time              `json:"creationTimestamp,omitempty"`
}

type ListMeta struct{}

type Time struct {
	time.Time
}

func (in *TypeMeta) DeepCopyInto(out *TypeMeta) { *out = *in }
func (in *ObjectMeta) DeepCopyInto(out *ObjectMeta) {
	*out = *in
	if in.Labels != nil {
		out.Labels = make(map[string]string, len(in.Labels))
		for key, value := range in.Labels {
			out.Labels[key] = value
		}
	}
}
func (in *ListMeta) DeepCopyInto(out *ListMeta) { *out = *in }
func (in *Time) DeepCopyInto(out *Time)         { *out = *in }

func AddToGroupVersion(*runtime.Scheme, any) {}
