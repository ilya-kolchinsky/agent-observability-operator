package controller_runtime

import (
	"context"

	"github.com/go-logr/logr"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
)

type Result struct{}

type Request struct {
	NamespacedName any
}

type Options struct {
	Scheme                 *runtime.Scheme
	Metrics                metricsserver.Options
	HealthProbeBindAddress string
	LeaderElection         bool
	LeaderElectionID       string
}

type Manager interface {
	GetClient() client.Client
	GetScheme() *runtime.Scheme
	AddHealthzCheck(string, any) error
	AddReadyzCheck(string, any) error
	Start(context.Context) error
}

type manager struct {
	client client.Client
	scheme *runtime.Scheme
}

func (m *manager) GetClient() client.Client          { return m.client }
func (m *manager) GetScheme() *runtime.Scheme        { return m.scheme }
func (m *manager) AddHealthzCheck(string, any) error { return nil }
func (m *manager) AddReadyzCheck(string, any) error  { return nil }
func (m *manager) Start(context.Context) error       { return nil }

var Log = logr.Logger{}

func SetLogger(logr.Logger)               {}
func GetConfigOrDie() any                 { return struct{}{} }
func SetupSignalHandler() context.Context { return context.Background() }
func NewManager(_ any, opts Options) (Manager, error) {
	return &manager{client: client.Client{}, scheme: opts.Scheme}, nil
}

type Builder struct{}

func NewControllerManagedBy(Manager) *Builder { return &Builder{} }
func (b *Builder) For(any) *Builder           { return b }
func (b *Builder) Named(string) *Builder      { return b }
func (b *Builder) Complete(any) error         { return nil }
