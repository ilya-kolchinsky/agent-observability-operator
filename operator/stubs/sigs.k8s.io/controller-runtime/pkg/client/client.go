package client

import "context"

type Object interface{}

type Client struct{}

func (Client) Get(context.Context, any, Object) error { return nil }
