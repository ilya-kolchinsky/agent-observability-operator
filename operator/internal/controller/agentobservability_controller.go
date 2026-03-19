package controller

import (
	"context"

	"github.com/go-logr/logr"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	platformv1alpha1 "github.com/example/agent-observability-operator/operator/api/v1alpha1"
)

// AgentObservabilityDemoReconciler reconciles an AgentObservabilityDemo object.
type AgentObservabilityDemoReconciler struct {
	client.Client
	Scheme *runtime.Scheme
	Log    logr.Logger
}

// Reconcile logs the requested spec and returns success.
// Future phases will validate the target workload, create/update generated
// resources such as Instrumentation and ConfigMaps, and report richer status.
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

	logger.Info("reconciliation requested",
		"generation", demo.Generation,
		"target", demo.Spec.Target,
		"instrumentation", demo.Spec.Instrumentation,
		"runtimeCoordinator", demo.Spec.RuntimeCoordinator,
		"demo", demo.Spec.Demo,
	)

	return ctrl.Result{}, nil
}

// SetupWithManager wires the controller into the manager.
// Future phases may add watches for owned resources like ConfigMaps or
// Instrumentation objects once the reconciliation logic manages them.
func (r *AgentObservabilityDemoReconciler) SetupWithManager(mgr ctrl.Manager) error {
	if r.Log.GetSink() == nil {
		r.Log = ctrl.Log.WithName("controllers").WithName("AgentObservabilityDemo")
	}

	return ctrl.NewControllerManagedBy(mgr).
		For(&platformv1alpha1.AgentObservabilityDemo{}).
		Named("agentobservabilitydemo").
		Complete(r)
}
