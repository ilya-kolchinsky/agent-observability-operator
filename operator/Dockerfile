FROM golang:1.22 AS builder
WORKDIR /workspace/operator

COPY operator/go.mod ./go.mod
COPY operator/stubs ./stubs
COPY operator/api ./api
COPY operator/internal ./internal
COPY operator/main.go ./main.go

RUN go build -o /out/agent-observability-operator ./main.go

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /out/agent-observability-operator /usr/local/bin/agent-observability-operator
USER nobody
ENTRYPOINT ["/usr/local/bin/agent-observability-operator"]
