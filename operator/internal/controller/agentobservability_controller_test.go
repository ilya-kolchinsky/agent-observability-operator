package controller

import (
	"testing"

	platformv1alpha1 "github.com/example/agent-observability-operator/operator/api/v1alpha1"
)

func TestBuildDesiredInstrumentationMapsCRSpec(t *testing.T) {
	demo := &platformv1alpha1.AgentObservabilityDemo{}
	demo.Name = "sample-demo"
	demo.Namespace = "operator-ns"
	demo.Spec.Target.Namespace = "target-ns"
	demo.Spec.Instrumentation.CustomPythonImage = "ghcr.io/example/custom-python:latest"
	demo.Spec.Instrumentation.OTelCollectorEndpoint = "http://otel-collector.default.svc.cluster.local:4317"

	instrumentation := buildDesiredInstrumentation(demo, demo.Spec.Target.Namespace)

	if instrumentation.Name != "sample-demo-instrumentation" {
		t.Fatalf("expected generated name, got %q", instrumentation.Name)
	}
	if instrumentation.Namespace != "target-ns" {
		t.Fatalf("expected target namespace, got %q", instrumentation.Namespace)
	}
	if instrumentation.Labels["managed-by"] != managedByLabelValue {
		t.Fatalf("expected managed-by label %q, got %q", managedByLabelValue, instrumentation.Labels["managed-by"])
	}
	if instrumentation.Spec.Python.Image != demo.Spec.Instrumentation.CustomPythonImage {
		t.Fatalf("expected python image %q, got %q", demo.Spec.Instrumentation.CustomPythonImage, instrumentation.Spec.Python.Image)
	}
	if instrumentation.Spec.Exporter.Endpoint != demo.Spec.Instrumentation.OTelCollectorEndpoint {
		t.Fatalf("expected collector endpoint %q, got %q", demo.Spec.Instrumentation.OTelCollectorEndpoint, instrumentation.Spec.Exporter.Endpoint)
	}
}

func TestInstrumentationDriftedDetectsSpecAndLabelChanges(t *testing.T) {
	demo := &platformv1alpha1.AgentObservabilityDemo{}
	demo.Name = "sample-demo"
	demo.Spec.Instrumentation.CustomPythonImage = "ghcr.io/example/custom-python:latest"
	demo.Spec.Instrumentation.OTelCollectorEndpoint = "http://otel-collector.default.svc.cluster.local:4317"

	desired := buildDesiredInstrumentation(demo, "default")
	matching := buildDesiredInstrumentation(demo, "default")
	if instrumentationDrifted(matching, desired) {
		t.Fatal("expected identical instrumentation to be treated as in sync")
	}

	matching.Spec.Python.Image = "ghcr.io/example/custom-python:new"
	if !instrumentationDrifted(matching, desired) {
		t.Fatal("expected python image drift to be detected")
	}
}
