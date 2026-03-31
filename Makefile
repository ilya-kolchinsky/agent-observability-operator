.PHONY: create-kind-cluster build-images build-core-images build-demo-images load-images-kind install-deps setup-ollama install-otel-operator install-collector install-jaeger deploy-operator deploy-demo-apps apply-sample-crs deploy verify-demo port-forward-jaeger send-demo-traffic demo-walkthrough demo operator-check-local clean

# Demo setup targets (use examples/end-to-end-demo/scripts/)
create-kind-cluster:
	./examples/end-to-end-demo/scripts/create-kind-cluster.sh

install-deps:
	./examples/end-to-end-demo/scripts/install-deps.sh

setup-ollama:
	./examples/end-to-end-demo/scripts/setup-ollama.sh

install-otel-operator:
	./examples/end-to-end-demo/scripts/install-otel-operator.sh

install-collector:
	./examples/end-to-end-demo/scripts/install-collector.sh

install-jaeger:
	./examples/end-to-end-demo/scripts/install-jaeger.sh

# Build targets
build-core-images:
	./core/scripts/build-core-images.sh

build-demo-images:
	./examples/end-to-end-demo/scripts/build-demo-images.sh

build-images: build-core-images build-demo-images

load-images-kind:
	./examples/end-to-end-demo/scripts/load-images-kind.sh

# Deployment targets
deploy-operator:
	./core/scripts/deploy-operator.sh

deploy-demo-apps:
	./examples/end-to-end-demo/scripts/deploy-demo-apps.sh

apply-sample-crs:
	./examples/end-to-end-demo/scripts/apply-sample-crs.sh

deploy: deploy-operator deploy-demo-apps apply-sample-crs

# Verification and demo targets
verify-demo:
	./examples/end-to-end-demo/scripts/verify-demo.sh

port-forward-jaeger:
	./examples/end-to-end-demo/scripts/port-forward-jaeger.sh

send-demo-traffic:
	./examples/end-to-end-demo/scripts/send-demo-traffic.sh

demo-walkthrough:
	./examples/end-to-end-demo/scripts/demo.sh

demo: demo-walkthrough

# Operator development
operator-check-local:
	./core/scripts/check-operator-local.sh

# Cleanup
clean:
	./examples/end-to-end-demo/scripts/clean.sh
