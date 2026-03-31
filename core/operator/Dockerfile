FROM golang:1.25 AS builder
WORKDIR /workspace/operator

COPY core/operator/go.mod ./go.mod
COPY core/operator/go.sum ./go.sum
COPY core/operator/api ./api
COPY core/operator/internal ./internal
COPY core/operator/main.go ./main.go

RUN go build -o /out/agent-observability-operator ./main.go

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /out/agent-observability-operator /usr/local/bin/agent-observability-operator
USER nobody
ENTRYPOINT ["/usr/local/bin/agent-observability-operator"]
