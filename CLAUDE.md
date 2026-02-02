# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
pytest

# Run single test file
pytest tests/test_models.py

# Run single test
pytest tests/test_models.py::test_semver_parsing -v

# Run with coverage
pytest --cov

# Lint
ruff check .

# Format
ruff format .

# Type check
mypy src
```

## Project Overview

Switchboard is a Python-first plugin runtime library providing host-owned, deterministic extensibility. It enables applications to define extension points (Slots and Hooks) that plugins can contribute to via manifests.

## Architecture

**Domain-Driven Design + Hexagonal Architecture (Ports & Adapters)**

### Core Concepts
- **PatchPanel**: Aggregate root - central registry, resolver, and runtime coordinator
- **Slot**: Named anchor point for contributions (UI or non-UI)
- **Hook**: Named interception point for events, commands, lifecycle
- **Contribution**: What plugins contribute to slots/hooks
- **Plugin lifecycle**: `ready → starting → active → stopping → ready` (plus `failed`)

### Internal Dependencies (V1)
- **Pluggy**: Hook dispatch (behind `HookRouterPort` / `PluggyHookRouter`)
- **Transitions**: Lifecycle state machine (internal to `PluginLifecycle`)
- **PyYAML**: Manifest parsing (in `application/manifest.py`)

These are internal implementation details - never expose Pluggy/Transitions types in public API.

### Target Package Structure
```
switchboard/
  domain/         # PatchPanel, lifecycle, models, policies, errors
  application/    # Use cases: register, activate, resolve, emit, diagnostics
  adapters/       # discovery/, loader/, persistence/, observability/
  schemas/        # JSON schemas (plugin_manifest.json)
  cli/            # Optional CLI adapter
```

### Key Invariants
- Plugins must be registered before activation
- Contributions only resolvable when plugin is `active`
- Slot/hook names unique within PatchPanel namespace
- Resolution is deterministic: priority → plugin_id → contribution_id tie-break
- Plugin code should not execute on import; side effects occur in `activate()`

## Design Documents

See `docs/` for full specifications:
- `SWITCHBOARD_INTENT_DOC.md` - Philosophy and design rationale
- `SWITCHBOARD_V1_ARCH_SPEC.md` - Complete V1 architecture specification
- `SWITCHBOARD_PATCHPANEL_SLOT_HOOK_ALIGNMENT.md` - Terminology alignment
