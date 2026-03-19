package v1alpha1

import (
	"k8s.io/apimachinery/pkg/runtime/schema"
	ctrlscheme "sigs.k8s.io/controller-runtime/pkg/scheme"
)

var (
	// GroupVersion is group version used to register these objects.
	GroupVersion = schema.GroupVersion{Group: "opentelemetry.io", Version: "v1alpha1"}

	// SchemeBuilder registers OpenTelemetry operator API types with a runtime scheme.
	SchemeBuilder = &ctrlscheme.Builder{GroupVersion: GroupVersion}

	// AddToScheme adds the OpenTelemetry operator API types to a runtime scheme.
	AddToScheme = SchemeBuilder.AddToScheme
)
