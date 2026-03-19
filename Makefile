.PHONY: build kind-up install-deps install-otel-operator install-collector install-jaeger deploy demo clean

build:
	@echo "TODO: build operator, images, and demo artifacts"

kind-up:
	@echo "TODO: create or reuse local kind cluster"

install-deps:
	./scripts/install-deps.sh

install-otel-operator:
	./scripts/install-otel-operator.sh

install-collector:
	./scripts/install-collector.sh

install-jaeger:
	./scripts/install-jaeger.sh

deploy:
	@echo "TODO: deploy operator, manifests, and demo resources"

demo:
	@echo "TODO: run end-to-end demo workflow"

clean:
	@echo "TODO: remove local PoC resources and artifacts"
