package v1

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

type Deployment struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              DeploymentSpec `json:"spec,omitempty"`
}

type DeploymentSpec struct {
	Template corev1.PodTemplateSpec `json:"template,omitempty"`
}
