# Documentation Index

This directory contains all documentation for the agent observability operator project.

## Getting Started

- **[Quick Start Guide](QUICKSTART.md)** - Build and run the demo from scratch
- **[Configuration Guide](CONFIGURATION.md)** - Configure AutoInstrumentation custom resources
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Diagnose and fix common issues

## Understanding the System

- **[Architecture](ARCHITECTURE.md)** - System design, components, and data flow
- **[Plugin Development Guide](PLUGIN_DEVELOPMENT.md)** - Add new instrumentation libraries

## Development

- **[Claude Code Instructions](CLAUDE.md)** - Guidelines for AI-assisted development with Claude Code

## Design Documents

The `design/` subdirectory contains historical design documents and research:

- **[Hybrid Solution Design](design/HYBRID_SOLUTION_DESIGN.md)** - Configuration + deferred ownership resolution approach
- **[Swap Mechanism Research](design/SWAP_MECHANISM_RESEARCH.md)** - Research on uninstrumentation patterns

## Quick Links

**I want to...**

- **Run the demo** → [Quick Start Guide](QUICKSTART.md)
- **Understand the architecture** → [Architecture](ARCHITECTURE.md)
- **Configure a workload** → [Configuration Guide](CONFIGURATION.md)
- **Fix an issue** → [Troubleshooting Guide](TROUBLESHOOTING.md)
- **Add a new library** → [Plugin Development Guide](PLUGIN_DEVELOPMENT.md)
- **Work with Claude Code** → [Claude Code Instructions](CLAUDE.md)

## External Documentation

For component-specific implementation details, see the README files in the source directories:

- `core/operator/README.md` - Operator implementation details (after refactoring)
- `core/runtime-coordinator/README.md` - Runtime coordinator implementation (after refactoring)
- `core/custom-python-image/README.md` - Custom Python image build details (after refactoring)
- `examples/end-to-end-demo/README.md` - Demo apps implementation (after refactoring)

Note: These paths reference the post-refactoring structure. During the transition, these files may still be at their original locations.
