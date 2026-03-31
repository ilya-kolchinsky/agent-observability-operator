#!/usr/bin/env sh
# Optional pass-through entrypoint kept for reference only.
# The image intentionally keeps the application startup command standard and
# relies on Python's sitecustomize import hook for coordinator bootstrapping.
exec "$@"
