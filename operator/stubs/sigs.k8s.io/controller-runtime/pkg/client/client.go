package client

import "context"

type Object interface{}

type ObjectKey struct {
	Namespace string
	Name      string
}

type StatusWriter struct{}

type Client struct{}

func (Client) Get(context.Context, any, Object) error             { return nil }
func (Client) Create(context.Context, Object, ...any) error       { return nil }
func (Client) Update(context.Context, Object, ...any) error       { return nil }
func (Client) Status() StatusWriter                               { return StatusWriter{} }
func (StatusWriter) Update(context.Context, Object, ...any) error { return nil }
