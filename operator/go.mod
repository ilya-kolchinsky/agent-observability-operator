module github.com/example/agent-observability-operator/operator

go 1.25

require (
	github.com/go-logr/logr v1.4.2
	github.com/open-telemetry/opentelemetry-operator v0.121.0
	k8s.io/api v0.32.3
	k8s.io/apimachinery v0.32.3
	k8s.io/client-go v0.32.3
	sigs.k8s.io/controller-runtime v0.20.4
)
