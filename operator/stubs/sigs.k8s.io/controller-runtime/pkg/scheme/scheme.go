package scheme

import (
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
)

type Builder struct {
	GroupVersion schema.GroupVersion
}

func (b *Builder) Register(...runtime.Object)        {}
func (b *Builder) AddToScheme(*runtime.Scheme) error { return nil }
