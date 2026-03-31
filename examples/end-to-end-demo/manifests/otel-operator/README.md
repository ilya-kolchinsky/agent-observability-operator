# OpenTelemetry Operator Install

This directory contains installation scripts for the upstream OpenTelemetry Operator.

## Installation Method

The demo uses **raw manifests** (not Helm) for installing the OpenTelemetry Operator.

## Install

```bash
examples/end-to-end-demo/scripts/install-otel-operator.sh
```

Or via Makefile:

```bash
make install-otel-operator
```

## What Gets Installed

1. **cert-manager** - Required dependency for the OpenTelemetry Operator
2. **OpenTelemetry Operator** - Upstream operator from official releases

The script waits for both deployments to become ready before completing.

## Version Configuration

Override versions using environment variables:

```bash
CERT_MANAGER_VERSION=v1.17.1 \
OTEL_OPERATOR_VERSION=v0.121.0 \
OTEL_OPERATOR_NAMESPACE=opentelemetry-operator-system \
examples/end-to-end-demo/scripts/install-otel-operator.sh
```

## Verify

Check that the operator is running:

```bash
kubectl get pods -n cert-manager
kubectl get pods -n opentelemetry-operator-system
```

## How It Works

The custom operator in this project generates `Instrumentation` resources that the OpenTelemetry Operator then uses to inject auto-instrumentation into target workloads.

**Workflow:**
1. User creates `AutoInstrumentation` CR
2. Custom operator reconciles it into:
   - OpenTelemetry `Instrumentation` resource
   - Runtime coordinator ConfigMap
   - Workload annotations
3. OpenTelemetry Operator sees the annotations and injects auto-instrumentation
4. Custom Python image with runtime coordinator starts

## See Also

- [Architecture](../../../../docs/ARCHITECTURE.md) - How the custom operator integrates with OTel Operator
- [Core Operator](../../../../core/operator/README.md) - Custom operator implementation
