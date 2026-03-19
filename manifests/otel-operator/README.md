# OpenTelemetry Operator Install Notes

The PoC installs the upstream OpenTelemetry Operator with **raw manifests**, not Helm.

For a local demo cluster (kind preferred), use:

```bash
./scripts/install-otel-operator.sh
```

What the script does:

1. Installs `cert-manager`, which the operator depends on.
2. Applies the pinned upstream OpenTelemetry Operator release manifest.
3. Waits for both deployments to become ready.

Version overrides are available through environment variables:

- `CERT_MANAGER_VERSION`
- `OTEL_OPERATOR_VERSION`
- `OTEL_OPERATOR_NAMESPACE`

This directory intentionally does **not** add Instrumentation resources yet; wiring our operator into the OpenTelemetry Operator comes in a later phase.
