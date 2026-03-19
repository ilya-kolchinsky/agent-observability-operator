module github.com/example/agent-observability-operator/operator

go 1.22

require (
	github.com/go-logr/logr v0.0.0
	k8s.io/apimachinery v0.0.0
	k8s.io/client-go v0.0.0
	sigs.k8s.io/controller-runtime v0.0.0
)

replace github.com/go-logr/logr => ./stubs/github.com/go-logr/logr
replace k8s.io/apimachinery => ./stubs/k8s.io/apimachinery
replace k8s.io/client-go => ./stubs/k8s.io/client-go
replace sigs.k8s.io/controller-runtime => ./stubs/sigs.k8s.io/controller-runtime
