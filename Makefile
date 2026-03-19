.PHONY: build-images load-images-kind install-deps install-otel-operator install-collector install-jaeger deploy-operator deploy-demo-apps apply-sample-crs deploy port-forward-jaeger send-demo-traffic demo clean

build-images:
	./scripts/build-images.sh

load-images-kind:
	./scripts/load-images-kind.sh

install-deps:
	./scripts/install-deps.sh

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

port-forward-jaeger:
	./scripts/port-forward-jaeger.sh

send-demo-traffic:
	./scripts/send-demo-traffic.sh

demo: send-demo-traffic

clean:
	./scripts/clean.sh
