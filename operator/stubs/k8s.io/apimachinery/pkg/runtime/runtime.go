package runtime

type Object interface {
	DeepCopyObject() Object
}

type Scheme struct{}

func NewScheme() *Scheme { return &Scheme{} }
