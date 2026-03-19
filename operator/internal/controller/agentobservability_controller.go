package controller

import (
	"context"
	"fmt"
	"reflect"

	"github.com/go-logr/logr"
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
	managedByLabelValue       = "agent-observability-demo-operator"
	instrumentationReadyPhase = "InstrumentationReady"
)

// AgentObservabilityDemoReconciler reconciles an AgentObservabilityDemo object.
type AgentObservabilityDemoReconciler struct {
	client.Client
	Scheme *runtime.Scheme
	Log    logr.Logger
}

// Reconcile creates or updates the generated OpenTelemetry Instrumentation resource
// so it reflects the desired custom resource state.
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

	desiredInstrumentation := buildDesiredInstrumentation(&demo, targetNamespace)
	var existingInstrumentation otelv1alpha1.Instrumentation
	err := r.Get(ctx, client.ObjectKey{
		Name:      desiredInstrumentation.Name,
		Namespace: desiredInstrumentation.Namespace,
	}, &existingInstrumentation)
	switch {
	case apierrors.IsNotFound(err):
		if err := r.Create(ctx, desiredInstrumentation); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info("created Instrumentation resource",
			"name", desiredInstrumentation.Name,
			"namespace", desiredInstrumentation.Namespace,
			"pythonImage", desiredInstrumentation.Spec.Python.Image,
			"collectorEndpoint", desiredInstrumentation.Spec.Exporter.Endpoint,
		)
	case err != nil:
		return ctrl.Result{}, err
	default:
		if instrumentationDrifted(&existingInstrumentation, desiredInstrumentation) {
			existingInstrumentation.Labels = desiredInstrumentation.Labels
			existingInstrumentation.Spec = desiredInstrumentation.Spec
			if err := r.Update(ctx, &existingInstrumentation); err != nil {
				return ctrl.Result{}, err
			}
			logger.Info("updated Instrumentation resource",
				"name", existingInstrumentation.Name,
				"namespace", existingInstrumentation.Namespace,
				"pythonImage", existingInstrumentation.Spec.Python.Image,
				"collectorEndpoint", existingInstrumentation.Spec.Exporter.Endpoint,
			)
		} else {
			logger.Info("Instrumentation resource already up to date",
				"name", existingInstrumentation.Name,
				"namespace", existingInstrumentation.Namespace,
			)
		}
	}

	statusChanged := false
	if demo.Status.GeneratedInstrumentationName != desiredInstrumentation.Name {
		demo.Status.GeneratedInstrumentationName = desiredInstrumentation.Name
		statusChanged = true
	}
	if demo.Status.Phase != instrumentationReadyPhase {
		demo.Status.Phase = instrumentationReadyPhase
		statusChanged = true
	}
	if demo.Status.ObservedGeneration != demo.Generation {
		demo.Status.ObservedGeneration = demo.Generation
		statusChanged = true
	}
	message := fmt.Sprintf("Instrumentation %s is ready in namespace %s", desiredInstrumentation.Name, desiredInstrumentation.Namespace)
	if demo.Status.Message != message {
		demo.Status.Message = message
		statusChanged = true
	}

	if statusChanged {
		if err := r.Status().Update(ctx, &demo); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info("updated AgentObservabilityDemo status",
			"phase", demo.Status.Phase,
			"generatedInstrumentationName", demo.Status.GeneratedInstrumentationName,
		)
		return ctrl.Result{}, nil
	}

	logger.Info("AgentObservabilityDemo status already up to date",
		"phase", demo.Status.Phase,
		"generatedInstrumentationName", demo.Status.GeneratedInstrumentationName,
	)

	return ctrl.Result{}, nil
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
			Exporter: otelv1alpha1.Exporter{
				Endpoint: demo.Spec.Instrumentation.OTelCollectorEndpoint,
			},
			Python: otelv1alpha1.Python{
				Image: demo.Spec.Instrumentation.CustomPythonImage,
			},
		},
	}
}

func generatedInstrumentationName(name string) string {
	return fmt.Sprintf("%s-instrumentation", name)
}

func instrumentationDrifted(existing *otelv1alpha1.Instrumentation, desired *otelv1alpha1.Instrumentation) bool {
	return !reflect.DeepEqual(existing.Labels, desired.Labels) || !reflect.DeepEqual(existing.Spec, desired.Spec)
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
