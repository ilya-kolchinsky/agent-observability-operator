# Troubleshooting Guide

This guide helps you diagnose and fix common issues with the agent observability operator.

## Quick Diagnostics Checklist

When something isn't working, run through this checklist:

1. **Cluster healthy?** → `kubectl get nodes`
2. **Operator running?** → `kubectl get pods -n agent-observability-system`
3. **CRs applied?** → `kubectl get autoinstrumentations -n demo-apps`
4. **Instrumentation generated?** → `kubectl get instrumentation -n demo-apps`
5. **Pods mutated?** → `kubectl describe pod -n demo-apps <pod-name>`
6. **Coordinator started?** → `kubectl logs -n demo-apps deployment/<workload>`
7. **Collector receiving?** → `kubectl logs -n observability deployment/demo-collector-collector`

## Common Issues

### No Traces in Jaeger

**Symptoms:**
- Jaeger UI shows no services or traces
- Search returns empty results

**Diagnostic steps:**

1. **Re-send traffic:**
   ```bash
   make send-demo-traffic
   ```

2. **Check Collector is receiving traces:**
   ```bash
   kubectl logs -n observability deployment/demo-collector-collector --tail=200
   ```

   Look for OTLP receive/export activity.

3. **Verify OTLP endpoint configuration:**
   ```bash
   kubectl get deployment -n demo-apps agent-no-existing -o yaml | grep OTEL_EXPORTER
   ```

   Should show: `http://agent-observability-collector.observability.svc.cluster.local:4318`

4. **Check Jaeger is healthy:**
   ```bash
   kubectl get pods -n observability
   kubectl logs -n observability deployment/jaeger --tail=200
   ```

5. **Verify app is actually sending spans:**
   ```bash
   kubectl logs -n demo-apps deployment/agent-no-existing --tail=100
   ```

   Look for coordinator startup diagnostics and no instrumentation errors.

**Common causes:**
- Collector or Jaeger pods not running
- Wrong OTLP endpoint in app configuration
- Coordinator failed to initialize provider
- No traffic sent to instrumented endpoints

### Pod Not Mutated for Injection

**Symptoms:**
- Pod lacks `instrumentation.opentelemetry.io/inject-python` annotation
- No OpenTelemetry init containers or volumes
- OTLP environment variables missing

**Diagnostic steps:**

1. **Verify custom resource exists and targets correct workload:**
   ```bash
   kubectl get autoinstrumentations -n demo-apps -o yaml
   ```

   Check:
   - `spec.target.workloadName` matches Deployment name
   - `spec.target.containerName` matches container in Deployment
   - `spec.target.namespace` is correct (or omitted for same namespace)

2. **Check generated Instrumentation resource:**
   ```bash
   kubectl get instrumentation -n demo-apps
   kubectl describe instrumentation <name>-instrumentation -n demo-apps
   ```

3. **Review operator reconciliation logs:**
   ```bash
   kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=200
   ```

   Look for:
   - "created Instrumentation resource"
   - "updated Deployment"
   - Any errors or warnings

4. **Check if Deployment template was patched:**
   ```bash
   kubectl get deployment -n demo-apps <workload-name> -o yaml | grep -A10 annotations
   ```

   Should see `instrumentation.opentelemetry.io` annotations.

5. **If Deployment changed but Pod didn't, force recreation:**
   ```bash
   kubectl delete pod -n demo-apps <agent-pod-name>
   ```

   Wait for Deployment to recreate it with new template.

**Common causes:**
- Wrong target workload name or namespace in CR
- Operator not reconciling (check operator logs)
- Deployment template not yet updated
- Old Pod still running with old template

### Operator Not Reconciling

**Symptoms:**
- Applied CR but no Instrumentation resource created
- Operator logs show no activity
- Status field not updated on CR

**Diagnostic steps:**

1. **Check operator is running:**
   ```bash
   kubectl get pods -n agent-observability-system
   ```

   Should show `agent-observability-operator` pod as Running.

2. **Check operator logs for errors:**
   ```bash
   kubectl logs -n agent-observability-system deployment/agent-observability-operator -f
   ```

   Look for:
   - Reconciliation start/complete messages
   - Any errors or stack traces
   - Permission denied errors (RBAC issues)

3. **Verify CRD is installed:**
   ```bash
   kubectl get crd autoinstrumentations.platform.example.com
   ```

4. **Check CR validation succeeded:**
   ```bash
   kubectl describe autoinstrumentation <name> -n <namespace>
   ```

   Look at Events section for validation errors.

5. **Verify RBAC permissions:**
   ```bash
   kubectl get clusterrole agent-observability-operator
   kubectl get clusterrolebinding agent-observability-operator
   ```

**Common causes:**
- Operator pod crashed or not running
- CRD not installed correctly
- CR validation failed (check Events)
- RBAC permissions missing
- Operator watching wrong namespace

### Runtime Coordinator Not Starting

**Symptoms:**
- Pod starts but coordinator diagnostics missing from logs
- App crashes immediately on startup
- Import errors in pod logs

**Diagnostic steps:**

1. **Check pod logs for startup failures:**
   ```bash
   kubectl logs -n demo-apps deployment/<workload> --tail=200
   ```

   Look for:
   - Python import errors
   - Coordinator bootstrap errors
   - Traceback from sitecustomize.py

2. **Verify coordinator ConfigMap was created and mounted:**
   ```bash
   kubectl get configmap -n demo-apps
   kubectl describe pod -n demo-apps <pod-name> | grep -A5 Mounts
   ```

3. **Check if custom Python image was loaded:**
   ```bash
   docker images | grep agent-observability/custom-python-autoinstrumentation
   kind get clusters
   ```

   If missing, rebuild and reload:
   ```bash
   make build-images
   make load-images-kind
   ```

4. **Verify init container injected successfully:**
   ```bash
   kubectl describe pod -n demo-apps <pod-name> | grep -A20 "Init Containers"
   ```

   Should see `opentelemetry-auto-instrumentation` init container.

5. **Check for sitecustomize.py presence:**
   ```bash
   kubectl exec -n demo-apps deployment/<workload> -- ls -la /otel-auto-instrumentation-python
   ```

**Common causes:**
- Custom Python image not built or loaded into kind
- OTel Operator not injecting init container
- ConfigMap not mounted correctly
- Python import errors in coordinator code
- Missing required packages in custom image

### Unexpected Coordinator Decisions

**Symptoms:**
- Coordinator instruments libraries you expected it to skip
- Coordinator skips libraries you expected it to instrument
- Decisions don't match CR configuration

**Diagnostic steps:**

1. **Check coordinator startup diagnostics:**
   ```bash
   kubectl logs -n demo-apps deployment/<workload> --tail=200 | grep -A50 detection_complete
   ```

   Or check the diagnostics file:
   ```bash
   kubectl exec -n demo-apps deployment/<workload> -- cat /tmp/runtime-coordinator-diagnostics.log
   ```

2. **Verify CR configuration:**
   ```bash
   kubectl get autoinstrumentation <name> -n demo-apps -o yaml
   ```

   Check:
   - `enableInstrumentation` value (explicit or inferred)
   - `tracerProvider` value (explicit or inferred)
   - Per-library field values (true/false/"auto")
   - `autoDetection` setting

3. **Check if using auto-detection:**
   - If `autoDetection: true`, coordinator defers decisions to runtime
   - Libraries may show different decisions than expected
   - Check if app code ran before coordinator (timing issue)

4. **Review config-driven decisions:**
   ```bash
   kubectl exec -n demo-apps deployment/<workload> -- cat /tmp/runtime-coordinator-diagnostics.log | jq .decisions
   ```

**Common causes:**
- Sitecustomize timing issue (coordinator runs before main.py)
- Misunderstanding of auto-detection vs explicit config
- CR inference logic not matching expectations
- App code not yet instrumented when coordinator detected

### Jaeger UI Not Accessible

**Symptoms:**
- Cannot connect to http://127.0.0.1:16686
- Port-forward command exits or hangs
- Connection refused errors

**Diagnostic steps:**

1. **Verify port-forward is still running:**
   ```bash
   make port-forward-jaeger
   ```

   Keep this terminal window open.

2. **Check if port 16686 is already in use:**
   ```bash
   lsof -i :16686
   ```

   If in use, try different local port:
   ```bash
   LOCAL_PORT=26686 make port-forward-jaeger
   ```

   Then open: http://127.0.0.1:26686

3. **Verify Jaeger Service and Pod exist:**
   ```bash
   kubectl get svc,pods -n observability | grep jaeger
   ```

   Should show both Service and Pod.

4. **Check Jaeger pod is healthy:**
   ```bash
   kubectl logs -n observability deployment/jaeger --tail=100
   ```

5. **Try direct service port-forward:**
   ```bash
   kubectl port-forward -n observability svc/jaeger 16686:16686
   ```

**Common causes:**
- Port-forward command not running
- Local port already in use
- Jaeger pod not running or crashed
- Service not created correctly

### Ollama-Related Issues

**Symptoms:**
- Demo agent pods failing to start
- Connection errors to Ollama in logs
- Timeouts during agent requests

**Diagnostic steps:**

1. **Verify Ollama is running locally:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

   Should return JSON with model list.

2. **Run Ollama setup script:**
   ```bash
   make setup-ollama
   ```

   This will:
   - Check if Ollama is installed
   - Start Ollama service if not running
   - Download phi model if missing

3. **Check agent pod logs for Ollama errors:**
   ```bash
   kubectl logs -n demo-apps deployment/agent-no-existing --tail=50
   ```

   Look for connection errors to `host.docker.internal:11434`.

4. **Verify phi model is available:**
   ```bash
   ollama list
   ```

   Should show `phi` in the list.

5. **Start Ollama manually if needed:**
   ```bash
   # In a separate terminal, keep running:
   ollama serve

   # In another terminal:
   ollama pull phi
   ```

**Common causes:**
- Ollama not installed
- Ollama service not running
- phi model not downloaded
- Firewall blocking localhost:11434

### Image Build Failures

**Symptoms:**
- `make build-images` fails
- Docker build errors
- Missing dependencies

**Diagnostic steps:**

1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **Build individual images to isolate issue:**
   ```bash
   cd operator && docker build -t agent-observability/operator:latest .
   cd custom-python-image && docker build -t agent-observability/custom-python-autoinstrumentation:latest ..
   ```

3. **Check for missing files:**
   - Ensure build context includes required files
   - Check Dockerfile COPY instructions

4. **Clear Docker build cache if corrupted:**
   ```bash
   docker builder prune
   ```

**Common causes:**
- Docker daemon not running
- Missing source files
- Network issues downloading dependencies
- Insufficient disk space

### Kind Cluster Issues

**Symptoms:**
- Cannot create cluster
- Images not loading
- Cluster not accessible

**Diagnostic steps:**

1. **Check existing clusters:**
   ```bash
   kind get clusters
   ```

2. **Delete and recreate cluster:**
   ```bash
   make clean
   make create-kind-cluster
   ```

3. **Verify kubectl context:**
   ```bash
   kubectl config current-context
   ```

   Should show `kind-kind`.

4. **Check cluster nodes:**
   ```bash
   kubectl get nodes
   ```

**Common causes:**
- Previous cluster not cleaned up
- Docker networking issues
- kubectl context pointing to wrong cluster

## Getting Help

### Collecting Diagnostic Information

When reporting issues, collect this information:

```bash
# Cluster info
kubectl version
kubectl get nodes

# Operator status
kubectl get pods -n agent-observability-system
kubectl logs -n agent-observability-system deployment/agent-observability-operator --tail=500

# Custom resources
kubectl get autoinstrumentations -A -o yaml
kubectl get instrumentation -A -o yaml

# Workload status
kubectl get pods -n demo-apps
kubectl describe pod -n demo-apps <pod-name>
kubectl logs -n demo-apps deployment/<workload> --tail=200

# Backend status
kubectl get pods -n observability
kubectl logs -n observability deployment/demo-collector-collector --tail=200
```

### Debug Mode

Enable verbose logging:

```bash
# Operator (rebuild with debug logging)
# Edit operator/main.go to increase log level

# Coordinator (check diagnostics file)
kubectl exec -n demo-apps deployment/<workload> -- cat /tmp/runtime-coordinator-diagnostics.log
```

### Known Limitations

Remember these known limitations when troubleshooting:

1. **Sitecustomize timing issue:** Coordinator runs before app's main.py, cannot detect what app will configure later
2. **Deployment-only support:** Only Deployment workloads supported, not StatefulSets/DaemonSets
3. **Local kind only:** Images built locally, not suitable for multi-node or remote clusters
4. **Simplified heuristics:** Detection is best-effort, not semantically perfect
5. **Demo infrastructure:** Jaeger uses ephemeral storage, traces lost on restart

## See Also

- [Quick Start Guide](QUICKSTART.md) - Setup instructions
- [Configuration Guide](CONFIGURATION.md) - CR configuration reference
- [Architecture](ARCHITECTURE.md) - System design details
