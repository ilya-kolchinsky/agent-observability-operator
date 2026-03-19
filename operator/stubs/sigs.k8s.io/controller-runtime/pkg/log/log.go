package log

import (
	"context"

	"github.com/go-logr/logr"
)

func FromContext(context.Context) logr.Logger { return logr.Logger{} }
