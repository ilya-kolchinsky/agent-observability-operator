package zap

import (
	"flag"

	"github.com/go-logr/logr"
)

type Options struct {
	Development bool
}

func (o *Options) BindFlags(*flag.FlagSet) {}

type option struct{}

func UseFlagOptions(*Options) option { return option{} }
func New(...option) logr.Logger      { return logr.Logger{} }
