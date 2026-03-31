.PHONY: create-kind-cluster build-images load-images-kind install-deps setup-ollama install-otel-operator install-collector install-jaeger deploy-operator deploy-demo-apps apply-sample-crs deploy verify-demo port-forward-jaeger send-demo-traffic demo-walkthrough demo operator-check-local clean

create-kind-cluster:
	./scripts/create-kind-cluster.sh

build-images:
	./scripts/build-images.sh

load-images-kind:
	./scripts/load-images-kind.sh

install-deps:
	./scripts/install-deps.sh

setup-ollama:
	./scripts/setup-ollama.sh

install-otel-operator:
	./scripts/install-otel-operator.sh

install-collector:
	./scripts/install-collector.sh

install-jaeger:
	./scripts/install-jaeger.sh

deploy-operator:
	./scripts/deploy-operator.sh

deploy-demo-apps:
	./scripts/deploy-demo-apps.sh

apply-sample-crs:
	./scripts/apply-sample-crs.sh

deploy: deploy-operator deploy-demo-apps apply-sample-crs

verify-demo:
	./scripts/verify-demo.sh

port-forward-jaeger:
	./scripts/port-forward-jaeger.sh

send-demo-traffic:
	./scripts/send-demo-traffic.sh

demo-walkthrough:
	./scripts/demo.sh

demo: demo-walkthrough

operator-check-local:
	./scripts/check-operator-local.sh

clean:
	./scripts/clean.sh
