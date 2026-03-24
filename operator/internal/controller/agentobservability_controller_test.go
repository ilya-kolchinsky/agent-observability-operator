package controller

import (
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"

	platformv1alpha1 "github.com/example/agent-observability-operator/operator/api/v1alpha1"
)

func TestBuildDesiredInstrumentationMapsCRSpec(t *testing.T) {
	demo := testDemo()

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

func TestBuildDesiredInstrumentationFallsBackToDefaultCollectorService(t *testing.T) {
	demo := testDemo()
	demo.Spec.Instrumentation.OTelCollectorEndpoint = ""

	instrumentation := buildDesiredInstrumentation(demo, demo.Spec.Target.Namespace)

	if instrumentation.Spec.Exporter.Endpoint != defaultCollectorEndpoint {
		t.Fatalf("expected default collector endpoint %q, got %q", defaultCollectorEndpoint, instrumentation.Spec.Exporter.Endpoint)
	}
}

func TestBuildDesiredRuntimeCoordinatorConfigMapMapsCRSpec(t *testing.T) {
	demo := testDemo()

	configMap := buildDesiredRuntimeCoordinatorConfigMap(demo, demo.Spec.Target.Namespace)

	if configMap.Name != "sample-demo-runtime-coordinator" {
		t.Fatalf("expected generated configmap name, got %q", configMap.Name)
	}
	if configMap.Namespace != "target-ns" {
		t.Fatalf("expected target namespace, got %q", configMap.Namespace)
	}
	config := configMap.Data[runtimeCoordinatorConfigMapKey]
	for _, expected := range []string{
		"runtimeCoordinator:",
		"diagnosticsLevel: \"basic\"",
		"detectFrameworkInstrumentation: true",
		"disableDuplicateInstrumentations: true",
		"exporterEndpoint: \"http://agent-observability-collector.observability.svc.cluster.local:4318\"",
		"tracesEndpoint: \"http://agent-observability-collector.observability.svc.cluster.local:4318/v1/traces\"",
		"protocol: \"http/protobuf\"",
		"serviceName: \"agent-chat\"",
		"deploymentName: \"agent-chat\"",
	} {
		if !contains(config, expected) {
			t.Fatalf("expected configmap data to contain %q, got:\n%s", expected, config)
		}
	}
}

func TestPrepareDeploymentForInstrumentationOnlyPatchesSelectedContainerAndIsIdempotent(t *testing.T) {
	demo := testDemo()
	instrumentation := buildDesiredInstrumentation(demo, demo.Spec.Target.Namespace)
	deployment := &appsv1.Deployment{}
	deployment.Name = "agent-chat"
	deployment.Namespace = "target-ns"
	deployment.Spec.Template.Spec.Containers = []corev1.Container{
		{Name: "app"},
		{Name: "sidecar", Env: []corev1.EnvVar{{Name: "UNCHANGED", Value: "true"}}},
	}

	changed, err := prepareDeploymentForInstrumentation(demo, deployment, instrumentation, "sample-demo-runtime-coordinator")
	if err != nil {
		t.Fatalf("expected deployment preparation to succeed, got error: %v", err)
	}
	if !changed {
		t.Fatal("expected first deployment preparation to report changes")
	}

	annotations := deployment.Spec.Template.Annotations
	if annotations[injectPythonAnnotation] != "target-ns/sample-demo-instrumentation" {
		t.Fatalf("expected inject-python annotation to reference instrumentation, got %q", annotations[injectPythonAnnotation])
	}
	if annotations[injectContainerNamesAnnotation] != "app" {
		t.Fatalf("expected container annotation for app, got %q", annotations[injectContainerNamesAnnotation])
	}

	appContainer := deployment.Spec.Template.Spec.Containers[0]
	for _, name := range []string{
		"OTEL_EXPORTER_OTLP_ENDPOINT",
		"OTEL_EXPORTER_OTLP_PROTOCOL",
		"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
		"OTEL_RESOURCE_ATTRIBUTES",
		runtimeCoordinatorConfigPathEnvName,
		"RUNTIME_COORDINATOR_CONFIG_MAP",
	} {
		if !envVarExists(appContainer.Env, name) {
			t.Fatalf("expected app container env var %q to be present", name)
		}
	}
	if len(appContainer.VolumeMounts) != 1 || appContainer.VolumeMounts[0].Name != runtimeCoordinatorVolumeName {
		t.Fatalf("expected app container runtime coordinator mount, got %#v", appContainer.VolumeMounts)
	}

	sidecar := deployment.Spec.Template.Spec.Containers[1]
	if len(sidecar.Env) != 1 || sidecar.Env[0].Name != "UNCHANGED" {
		t.Fatalf("expected sidecar env to remain unchanged, got %#v", sidecar.Env)
	}
	if len(sidecar.VolumeMounts) != 0 {
		t.Fatalf("expected sidecar volume mounts to remain unchanged, got %#v", sidecar.VolumeMounts)
	}
	if len(deployment.Spec.Template.Spec.Volumes) != 1 || deployment.Spec.Template.Spec.Volumes[0].Name != runtimeCoordinatorVolumeName {
		t.Fatalf("expected runtime coordinator volume to be added, got %#v", deployment.Spec.Template.Spec.Volumes)
	}

	changed, err = prepareDeploymentForInstrumentation(demo, deployment, instrumentation, "sample-demo-runtime-coordinator")
	if err != nil {
		t.Fatalf("expected idempotent deployment preparation to succeed, got error: %v", err)
	}
	if changed {
		t.Fatal("expected second deployment preparation to be idempotent")
	}
}

func TestPrepareDeploymentForInstrumentationErrorsWhenContainerMissing(t *testing.T) {
	demo := testDemo()
	instrumentation := buildDesiredInstrumentation(demo, demo.Spec.Target.Namespace)
	deployment := &appsv1.Deployment{}
	deployment.Name = "agent-chat"
	deployment.Namespace = "target-ns"
	deployment.Spec.Template.Spec.Containers = []corev1.Container{{Name: "sidecar"}}

	changed, err := prepareDeploymentForInstrumentation(demo, deployment, instrumentation, "sample-demo-runtime-coordinator")
	if err == nil {
		t.Fatal("expected missing target container to return an error")
	}
	if changed {
		t.Fatal("expected no changes when target container is missing")
	}
}

func TestInstrumentationDriftedDetectsSpecAndLabelChanges(t *testing.T) {
	demo := testDemo()

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

func testDemo() *platformv1alpha1.AgentObservabilityDemo {
	demo := &platformv1alpha1.AgentObservabilityDemo{}
	demo.Name = "sample-demo"
	demo.Namespace = "operator-ns"
	demo.Spec.Target.Namespace = "target-ns"
	demo.Spec.Target.WorkloadName = "agent-chat"
	demo.Spec.Target.WorkloadKind = "Deployment"
	demo.Spec.Target.ContainerName = "app"
	demo.Spec.Instrumentation.CustomPythonImage = "agent-observability/custom-python-autoinstrumentation:latest"
	demo.Spec.Instrumentation.OTelCollectorEndpoint = defaultCollectorEndpoint
	demo.Spec.RuntimeCoordinator.Enabled = true
	demo.Spec.RuntimeCoordinator.DiagnosticsLevel = "basic"
	demo.Spec.RuntimeCoordinator.Heuristics.DetectExistingProvider = true
	demo.Spec.RuntimeCoordinator.Heuristics.DetectSpanProcessors = true
	demo.Spec.RuntimeCoordinator.Heuristics.DetectFrameworkInstrumentation = true
	demo.Spec.RuntimeCoordinator.Heuristics.DetectKnownVendorTracing = true
	demo.Spec.RuntimeCoordinator.Patchers.HTTPClient = true
	demo.Spec.RuntimeCoordinator.Patchers.GRPCClient = true
	demo.Spec.RuntimeCoordinator.Patchers.ASGI = true
	demo.Spec.RuntimeCoordinator.Patchers.GenAIOpenAI = true
	demo.Spec.RuntimeCoordinator.Patchers.MCPBoundary = true
	demo.Spec.RuntimeCoordinator.Suppression.DisableDuplicateInstrumentations = true
	return demo
}

func envVarExists(envVars []corev1.EnvVar, name string) bool {
	for _, envVar := range envVars {
		if envVar.Name == name {
			return true
		}
	}
	return false
}

func contains(haystack, needle string) bool {
	return len(needle) == 0 || (len(haystack) >= len(needle) && stringContains(haystack, needle))
}

func stringContains(haystack, needle string) bool {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return true
		}
	}
	return false
}
