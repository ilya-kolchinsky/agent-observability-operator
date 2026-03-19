package v1

import metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

type ConfigMap struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Data              map[string]string `json:"data,omitempty"`
}

type PodTemplateSpec struct {
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              PodSpec `json:"spec,omitempty"`
}

type PodSpec struct {
	Containers []Container `json:"containers,omitempty"`
	Volumes    []Volume    `json:"volumes,omitempty"`
}

type Container struct {
	Name         string        `json:"name,omitempty"`
	Env          []EnvVar      `json:"env,omitempty"`
	VolumeMounts []VolumeMount `json:"volumeMounts,omitempty"`
}

type EnvVar struct {
	Name  string `json:"name,omitempty"`
	Value string `json:"value,omitempty"`
}

type Volume struct {
	Name         string       `json:"name,omitempty"`
	VolumeSource VolumeSource `json:"volumeSource,omitempty"`
}

type VolumeSource struct {
	ConfigMap *ConfigMapVolumeSource `json:"configMap,omitempty"`
}

type ConfigMapVolumeSource struct {
	LocalObjectReference LocalObjectReference `json:"localObjectReference,omitempty"`
	Items                []KeyToPath          `json:"items,omitempty"`
}

type LocalObjectReference struct {
	Name string `json:"name,omitempty"`
}

type KeyToPath struct {
	Key  string `json:"key,omitempty"`
	Path string `json:"path,omitempty"`
}

type VolumeMount struct {
	Name      string `json:"name,omitempty"`
	MountPath string `json:"mountPath,omitempty"`
	ReadOnly  bool   `json:"readOnly,omitempty"`
}
