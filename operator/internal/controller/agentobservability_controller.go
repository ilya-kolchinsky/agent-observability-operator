package controller

import (
	"context"
	"fmt"
	"path"
	"reflect"
	"strings"

	"github.com/go-logr/logr"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	platformv1alpha1 "github.com/example/agent-observability-operator/operator/api/v1alpha1"
	otelv1alpha1 "github.com/open-telemetry/opentelemetry-operator/apis/v1alpha1"
)

const (
	managedByLabelValue                 = "agent-observability-demo-operator"
	workloadPreparedPhase               = "WorkloadPrepared"
	injectPythonAnnotation              = "instrumentation.opentelemetry.io/inject-python"
	injectContainerNamesAnnotation      = "instrumentation.opentelemetry.io/container-names"
	runtimeCoordinatorConfigMapKey      = "runtime-coordinator.yaml"
	runtimeCoordinatorConfigDir         = "/etc/agent-observability"
	runtimeCoordinatorConfigPathEnvName = "RUNTIME_COORDINATOR_CONFIG_FILE"
	runtimeCoordinatorVolumeName        = "agent-observability-runtime-config"
	defaultCollectorEndpoint            = "http://agent-observability-collector.observability.svc.cluster.local:4318"
	defaultCollectorProtocol            = "http/protobuf"
)

// AgentObservabilityDemoReconciler reconciles an AgentObservabilityDemo object.
type AgentObservabilityDemoReconciler struct {
	client.Client
	Scheme *runtime.Scheme
	Log    logr.Logger
}

// Reconcile creates or updates the generated OpenTelemetry Instrumentation resource
// and prepares the target Deployment for Python auto-instrumentation injection.
func (r *AgentObservabilityDemoReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)
	if r.Log.GetSink() != nil {
		logger = r.Log.WithValues("agentObservabilityDemo", req.NamespacedName)
	}

	var demo platformv1alpha1.AgentObservabilityDemo
	if err := r.Get(ctx, req.NamespacedName, &demo); err != nil {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, err
	}

	targetNamespace := demo.Spec.Target.Namespace
	if targetNamespace == "" {
		targetNamespace = demo.Namespace
	}
	if demo.Spec.Target.WorkloadKind != "" && demo.Spec.Target.WorkloadKind != "Deployment" {
		return ctrl.Result{}, fmt.Errorf("unsupported target workload kind %q: only Deployment is supported for this PoC", demo.Spec.Target.WorkloadKind)
	}

	collectorEndpoint := collectorEndpointForDemo(&demo)
	logger.Info(
		"reconciling AgentObservabilityDemo for end-to-end telemetry path",
		"targetNamespace", targetNamespace,
		"targetWorkload", demo.Spec.Target.WorkloadName,
		"targetContainer", demo.Spec.Target.ContainerName,
		"collectorEndpoint", collectorEndpoint,
	)

	desiredInstrumentation := buildDesiredInstrumentation(&demo, targetNamespace)
	if err := r.reconcileInstrumentation(ctx, logger, desiredInstrumentation); err != nil {
		return ctrl.Result{}, err
	}

	desiredConfigMap := buildDesiredRuntimeCoordinatorConfigMap(&demo, targetNamespace)
	if err := r.reconcileConfigMap(ctx, logger, desiredConfigMap); err != nil {
		return ctrl.Result{}, err
	}

	var targetDeployment appsv1.Deployment
	targetKey := client.ObjectKey{Name: demo.Spec.Target.WorkloadName, Namespace: targetNamespace}
	if err := r.Get(ctx, targetKey, &targetDeployment); err != nil {
		return ctrl.Result{}, err
	}
	changed, err := prepareDeploymentForInstrumentation(&demo, &targetDeployment, desiredInstrumentation, desiredConfigMap.Name)
	if err != nil {
		return ctrl.Result{}, err
	}
	if changed {
		if err := r.Update(ctx, &targetDeployment); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info(
			"updated target Deployment for instrumentation injection",
			"name", targetDeployment.Name,
			"namespace", targetDeployment.Namespace,
			"container", demo.Spec.Target.ContainerName,
			"configMap", desiredConfigMap.Name,
			"collectorEndpoint", collectorEndpoint,
			"collectorTracesEndpoint", collectorTracesEndpointForDemo(&demo),
		)
	} else {
		logger.Info(
			"target Deployment already prepared for instrumentation injection",
			"name", targetDeployment.Name,
			"namespace", targetDeployment.Namespace,
			"container", demo.Spec.Target.ContainerName,
			"collectorEndpoint", collectorEndpoint,
		)
	}

	statusChanged := false
	if demo.Status.GeneratedInstrumentationName != desiredInstrumentation.Name {
		demo.Status.GeneratedInstrumentationName = desiredInstrumentation.Name
		statusChanged = true
	}
	if demo.Status.GeneratedConfigMapName != desiredConfigMap.Name {
		demo.Status.GeneratedConfigMapName = desiredConfigMap.Name
		statusChanged = true
	}
	targetRef := fmt.Sprintf("Deployment/%s", targetKey.Name)
	if demo.Status.TargetWorkloadRef != targetRef {
		demo.Status.TargetWorkloadRef = targetRef
		statusChanged = true
	}
	if demo.Status.Phase != workloadPreparedPhase {
		demo.Status.Phase = workloadPreparedPhase
		statusChanged = true
	}
	if demo.Status.ObservedGeneration != demo.Generation {
		demo.Status.ObservedGeneration = demo.Generation
		statusChanged = true
	}
	message := fmt.Sprintf(
		"Deployment %s in namespace %s is prepared for OpenTelemetry injection using Instrumentation %s and ConfigMap %s with collector endpoint %s",
		targetDeployment.Name,
		targetDeployment.Namespace,
		desiredInstrumentation.Name,
		desiredConfigMap.Name,
		collectorEndpoint,
	)
	if demo.Status.Message != message {
		demo.Status.Message = message
		statusChanged = true
	}

	if statusChanged {
		if err := r.Status().Update(ctx, &demo); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info(
			"updated AgentObservabilityDemo status after reconciliation",
			"phase", demo.Status.Phase,
			"generatedInstrumentationName", demo.Status.GeneratedInstrumentationName,
			"generatedConfigMapName", demo.Status.GeneratedConfigMapName,
			"message", demo.Status.Message,
		)
		return ctrl.Result{}, nil
	}

	logger.Info(
		"AgentObservabilityDemo status already up to date",
		"phase", demo.Status.Phase,
		"generatedInstrumentationName", demo.Status.GeneratedInstrumentationName,
		"generatedConfigMapName", demo.Status.GeneratedConfigMapName,
	)

	return ctrl.Result{}, nil
}

func (r *AgentObservabilityDemoReconciler) reconcileInstrumentation(ctx context.Context, logger logr.Logger, desiredInstrumentation *otelv1alpha1.Instrumentation) error {
	var existingInstrumentation otelv1alpha1.Instrumentation
	err := r.Get(ctx, client.ObjectKey{
		Name:      desiredInstrumentation.Name,
		Namespace: desiredInstrumentation.Namespace,
	}, &existingInstrumentation)
	switch {
	case apierrors.IsNotFound(err):
		if err := r.Create(ctx, desiredInstrumentation); err != nil {
			return err
		}
		logger.Info(
			"created Instrumentation resource",
			"name", desiredInstrumentation.Name,
			"namespace", desiredInstrumentation.Namespace,
			"pythonImage", desiredInstrumentation.Spec.Python.Image,
			"collectorEndpoint", desiredInstrumentation.Spec.Exporter.Endpoint,
		)
	case err != nil:
		return err
	default:
		if instrumentationDrifted(&existingInstrumentation, desiredInstrumentation) {
			existingInstrumentation.Labels = desiredInstrumentation.Labels
			existingInstrumentation.Spec = desiredInstrumentation.Spec
			if err := r.Update(ctx, &existingInstrumentation); err != nil {
				return err
			}
			logger.Info(
				"updated Instrumentation resource",
				"name", existingInstrumentation.Name,
				"namespace", existingInstrumentation.Namespace,
				"pythonImage", existingInstrumentation.Spec.Python.Image,
				"collectorEndpoint", existingInstrumentation.Spec.Exporter.Endpoint,
			)
		} else {
			logger.Info(
				"Instrumentation resource already up to date",
				"name", existingInstrumentation.Name,
				"namespace", existingInstrumentation.Namespace,
			)
		}
	}

	return nil
}

func (r *AgentObservabilityDemoReconciler) reconcileConfigMap(ctx context.Context, logger logr.Logger, desiredConfigMap *corev1.ConfigMap) error {
	var existingConfigMap corev1.ConfigMap
	err := r.Get(ctx, client.ObjectKey{Name: desiredConfigMap.Name, Namespace: desiredConfigMap.Namespace}, &existingConfigMap)
	switch {
	case apierrors.IsNotFound(err):
		if err := r.Create(ctx, desiredConfigMap); err != nil {
			return err
		}
		logger.Info(
			"created runtime coordinator ConfigMap",
			"name", desiredConfigMap.Name,
			"namespace", desiredConfigMap.Namespace,
		)
	case err != nil:
		return err
	default:
		if configMapDrifted(&existingConfigMap, desiredConfigMap) {
			existingConfigMap.Labels = desiredConfigMap.Labels
			existingConfigMap.Data = desiredConfigMap.Data
			if err := r.Update(ctx, &existingConfigMap); err != nil {
				return err
			}
			logger.Info(
				"updated runtime coordinator ConfigMap",
				"name", existingConfigMap.Name,
				"namespace", existingConfigMap.Namespace,
			)
		} else {
			logger.Info(
				"runtime coordinator ConfigMap already up to date",
				"name", existingConfigMap.Name,
				"namespace", existingConfigMap.Namespace,
			)
		}
	}

	return nil
}

func buildDesiredInstrumentation(demo *platformv1alpha1.AgentObservabilityDemo, namespace string) *otelv1alpha1.Instrumentation {
	return &otelv1alpha1.Instrumentation{
		TypeMeta: metav1.TypeMeta{
			Kind:       "Instrumentation",
			APIVersion: otelv1alpha1.GroupVersion.Group + "/" + otelv1alpha1.GroupVersion.Version,
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      generatedInstrumentationName(demo.Name),
			Namespace: namespace,
			Labels: map[string]string{
				"managed-by": managedByLabelValue,
			},
		},
		Spec: otelv1alpha1.InstrumentationSpec{
		    ImagePullPolicy: corev1.PullIfNotPresent,
			Exporter: otelv1alpha1.Exporter{
				Endpoint: collectorEndpointForDemo(demo),
			},
			Python: otelv1alpha1.Python{
				Image: demo.Spec.Instrumentation.CustomPythonImage,
			},
		},
	}
}

func buildDesiredRuntimeCoordinatorConfigMap(demo *platformv1alpha1.AgentObservabilityDemo, namespace string) *corev1.ConfigMap {
	return &corev1.ConfigMap{
		TypeMeta: metav1.TypeMeta{
			Kind:       "ConfigMap",
			APIVersion: "v1",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      generatedRuntimeCoordinatorConfigMapName(demo.Name),
			Namespace: namespace,
			Labels: map[string]string{
				"managed-by": managedByLabelValue,
			},
		},
		Data: map[string]string{
			runtimeCoordinatorConfigMapKey: renderRuntimeCoordinatorConfig(demo, namespace),
		},
	}
}

func renderRuntimeCoordinatorConfig(demo *platformv1alpha1.AgentObservabilityDemo, namespace string) string {
	serviceName := desiredServiceName(demo)
	collectorEndpoint := collectorEndpointForDemo(demo)

	lines := []string{
		"runtimeCoordinator:",
		fmt.Sprintf("  enabled: %t", demo.Spec.RuntimeCoordinator.Enabled),
		fmt.Sprintf("  diagnosticsLevel: %s", yamlStringValue(demo.Spec.RuntimeCoordinator.DiagnosticsLevel)),
		"  heuristics:",
		fmt.Sprintf("    detectExistingProvider: %t", demo.Spec.RuntimeCoordinator.Heuristics.DetectExistingProvider),
		fmt.Sprintf("    detectSpanProcessors: %t", demo.Spec.RuntimeCoordinator.Heuristics.DetectSpanProcessors),
		fmt.Sprintf("    detectFrameworkInstrumentation: %t", demo.Spec.RuntimeCoordinator.Heuristics.DetectFrameworkInstrumentation),
		fmt.Sprintf("    detectKnownVendorTracing: %t", demo.Spec.RuntimeCoordinator.Heuristics.DetectKnownVendorTracing),
		"  patchers:",
		fmt.Sprintf("    httpClient: %t", demo.Spec.RuntimeCoordinator.Patchers.HTTPClient),
		fmt.Sprintf("    grpcClient: %t", demo.Spec.RuntimeCoordinator.Patchers.GRPCClient),
		fmt.Sprintf("    asgi: %t", demo.Spec.RuntimeCoordinator.Patchers.ASGI),
		fmt.Sprintf("    wsgi: %t", demo.Spec.RuntimeCoordinator.Patchers.WSGI),
		fmt.Sprintf("    genaiOpenAI: %t", demo.Spec.RuntimeCoordinator.Patchers.GenAIOpenAI),
		fmt.Sprintf("    mcpBoundary: %t", demo.Spec.RuntimeCoordinator.Patchers.MCPBoundary),
		"  suppression:",
		fmt.Sprintf("    disableDuplicateInstrumentations: %t", demo.Spec.RuntimeCoordinator.Suppression.DisableDuplicateInstrumentations),
		"telemetry:",
		fmt.Sprintf("  exporterEndpoint: %s", yamlStringValue(collectorEndpoint)),
		fmt.Sprintf("  tracesEndpoint: %s", yamlStringValue(collectorTracesEndpointForDemo(demo))),
		fmt.Sprintf("  protocol: %s", yamlStringValue(defaultCollectorProtocol)),
		fmt.Sprintf("  serviceName: %s", yamlStringValue(serviceName)),
		fmt.Sprintf("  serviceNamespace: %s", yamlStringValue(namespace)),
		fmt.Sprintf("  deploymentName: %s", yamlStringValue(demo.Spec.Target.WorkloadName)),
	}

	return strings.Join(lines, "\n") + "\n"
}

func generatedInstrumentationName(name string) string {
	return fmt.Sprintf("%s-instrumentation", name)
}

func generatedRuntimeCoordinatorConfigMapName(name string) string {
	return fmt.Sprintf("%s-runtime-coordinator", name)
}

func instrumentationReference(instrumentation *otelv1alpha1.Instrumentation) string {
	if instrumentation.Namespace == "" {
		return instrumentation.Name
	}
	return fmt.Sprintf("%s/%s", instrumentation.Namespace, instrumentation.Name)
}

func prepareDeploymentForInstrumentation(demo *platformv1alpha1.AgentObservabilityDemo, deployment *appsv1.Deployment, instrumentation *otelv1alpha1.Instrumentation, configMapName string) (bool, error) {
	containerIndex := findContainerIndex(deployment.Spec.Template.Spec.Containers, demo.Spec.Target.ContainerName)
	if containerIndex < 0 {
		return false, fmt.Errorf("target container %q not found in Deployment %s/%s", demo.Spec.Target.ContainerName, deployment.Namespace, deployment.Name)
	}

	changed := false
	if deployment.Spec.Template.Annotations == nil {
		deployment.Spec.Template.Annotations = map[string]string{}
	}
	if ensureAnnotation(deployment.Spec.Template.Annotations, injectPythonAnnotation, instrumentationReference(instrumentation)) {
		changed = true
	}
	if ensureAnnotation(deployment.Spec.Template.Annotations, injectContainerNamesAnnotation, demo.Spec.Target.ContainerName) {
		changed = true
	}

	container := &deployment.Spec.Template.Spec.Containers[containerIndex]
	for _, envVar := range desiredContainerEnvVars(demo, deployment.Namespace, configMapName) {
		if upsertEnvVar(container, envVar) {
			changed = true
		}
	}
	if ensureVolume(&deployment.Spec.Template.Spec, desiredRuntimeCoordinatorVolume(configMapName)) {
		changed = true
	}
	if ensureVolumeMount(container, desiredRuntimeCoordinatorVolumeMount()) {
		changed = true
	}

	return changed, nil
}

func desiredContainerEnvVars(demo *platformv1alpha1.AgentObservabilityDemo, workloadNamespace, configMapName string) []corev1.EnvVar {
	serviceName := desiredServiceName(demo)
	collectorEndpoint := collectorEndpointForDemo(demo)
	collectorTracesEndpoint := collectorTracesEndpointForDemo(demo)
	resourceAttributes := fmt.Sprintf("service.name=%s,service.namespace=%s,k8s.namespace.name=%s,k8s.deployment.name=%s", serviceName, workloadNamespace, workloadNamespace, demo.Spec.Target.WorkloadName)

	return []corev1.EnvVar{
		{Name: "OTEL_EXPORTER_OTLP_ENDPOINT", Value: collectorEndpoint},
		{Name: "OTEL_EXPORTER_OTLP_PROTOCOL", Value: defaultCollectorProtocol},
		{Name: "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", Value: collectorTracesEndpoint},
		{Name: "DEMO_OTLP_TRACES_ENDPOINT", Value: collectorTracesEndpoint},
		{Name: "OTEL_SERVICE_NAME", Value: serviceName},
		{Name: "OTEL_RESOURCE_ATTRIBUTES", Value: resourceAttributes},
		{Name: runtimeCoordinatorConfigPathEnvName, Value: runtimeCoordinatorConfigDir + "/" + runtimeCoordinatorConfigMapKey},
		{Name: "RUNTIME_COORDINATOR_CONFIG_MAP", Value: configMapName},
	}
}

func desiredServiceName(demo *platformv1alpha1.AgentObservabilityDemo) string {
	if demo.Spec.Target.WorkloadName != "" {
		return demo.Spec.Target.WorkloadName
	}
	return demo.Name
}

func desiredRuntimeCoordinatorVolume(configMapName string) corev1.Volume {
	return corev1.Volume{
		Name: runtimeCoordinatorVolumeName,
		VolumeSource: corev1.VolumeSource{
			ConfigMap: &corev1.ConfigMapVolumeSource{
				LocalObjectReference: corev1.LocalObjectReference{Name: configMapName},
				Items:                []corev1.KeyToPath{{Key: runtimeCoordinatorConfigMapKey, Path: runtimeCoordinatorConfigMapKey}},
			},
		},
	}
}

func desiredRuntimeCoordinatorVolumeMount() corev1.VolumeMount {
	return corev1.VolumeMount{
		Name:      runtimeCoordinatorVolumeName,
		MountPath: runtimeCoordinatorConfigDir,
		ReadOnly:  true,
	}
}

func configMapDrifted(existing *corev1.ConfigMap, desired *corev1.ConfigMap) bool {
	return !reflect.DeepEqual(existing.Labels, desired.Labels) || !reflect.DeepEqual(existing.Data, desired.Data)
}

func instrumentationDrifted(existing *otelv1alpha1.Instrumentation, desired *otelv1alpha1.Instrumentation) bool {
	return !reflect.DeepEqual(existing.Labels, desired.Labels) || !reflect.DeepEqual(existing.Spec, desired.Spec)
}

func ensureAnnotation(annotations map[string]string, key, value string) bool {
	if annotations[key] == value {
		return false
	}
	annotations[key] = value
	return true
}

func upsertEnvVar(container *corev1.Container, envVar corev1.EnvVar) bool {
	for i := range container.Env {
		if container.Env[i].Name == envVar.Name {
			if container.Env[i].Value == envVar.Value {
				return false
			}
			container.Env[i].Value = envVar.Value
			return true
		}
	}
	container.Env = append(container.Env, envVar)
	return true
}

func ensureVolume(spec *corev1.PodSpec, desired corev1.Volume) bool {
	for i := range spec.Volumes {
		if spec.Volumes[i].Name == desired.Name {
			if reflect.DeepEqual(spec.Volumes[i], desired) {
				return false
			}
			spec.Volumes[i] = desired
			return true
		}
	}
	spec.Volumes = append(spec.Volumes, desired)
	return true
}

func ensureVolumeMount(container *corev1.Container, desired corev1.VolumeMount) bool {
	for i := range container.VolumeMounts {
		if container.VolumeMounts[i].Name == desired.Name {
			if reflect.DeepEqual(container.VolumeMounts[i], desired) {
				return false
			}
			container.VolumeMounts[i] = desired
			return true
		}
	}
	container.VolumeMounts = append(container.VolumeMounts, desired)
	return true
}

func findContainerIndex(containers []corev1.Container, containerName string) int {
	for i := range containers {
		if containers[i].Name == containerName {
			return i
		}
	}
	return -1
}

func yamlStringValue(value string) string {
	if value == "" {
		return `""`
	}
	return fmt.Sprintf("%q", value)
}

func collectorEndpointForDemo(demo *platformv1alpha1.AgentObservabilityDemo) string {
	if strings.TrimSpace(demo.Spec.Instrumentation.OTelCollectorEndpoint) == "" {
		return defaultCollectorEndpoint
	}
	return strings.TrimRight(strings.TrimSpace(demo.Spec.Instrumentation.OTelCollectorEndpoint), "/")
}

func collectorTracesEndpointForDemo(demo *platformv1alpha1.AgentObservabilityDemo) string {
	endpoint := collectorEndpointForDemo(demo)
	if strings.HasSuffix(endpoint, "/v1/traces") {
		return endpoint
	}
	return strings.TrimRight(endpoint, "/") + path.Clean("/v1/traces")
}

// SetupWithManager wires the controller into the manager.
func (r *AgentObservabilityDemoReconciler) SetupWithManager(mgr ctrl.Manager) error {
	if r.Log.GetSink() == nil {
		r.Log = ctrl.Log.WithName("controllers").WithName("AgentObservabilityDemo")
	}

	return ctrl.NewControllerManagedBy(mgr).
		For(&platformv1alpha1.AgentObservabilityDemo{}).
		Named("agentobservabilitydemo").
		Complete(r)
}
