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

# Run smoke test
PYTHONPATH=. python examples/smoke_test.py
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

### Internal Dependencies
- **Pluggy**: Hook dispatch (behind `HookRouterPort` / `PluggyHookRouter`)
- **Transitions**: Lifecycle state machine (internal to `PluginLifecycle`)
- **PyYAML**: Manifest parsing (in `application/manifest.py`)

These are internal implementation details - never expose Pluggy/Transitions types in public API.

### Package Structure
```
switchboard/
  domain/         # PatchPanel, lifecycle, models, policies, errors
  application/    # Use cases: manifest parsing
  adapters/       # hook_router_memory, hook_router_pluggy, loader
```

### Key Invariants
- Plugins must be registered before activation
- Contributions only resolvable when plugin is `active`
- Slot/hook names unique within PatchPanel namespace
- Resolution is deterministic: priority → plugin_id → contribution_id tie-break
- Plugin code should not execute on import; side effects occur in `activate()`

## V2 API (Introspection & Dependencies)

### Introspection
```python
# Quick runtime overview
info = panel.runtime_info()  # -> RuntimeInfo

# Full state snapshot
snap = panel.snapshot()  # -> RuntimeSnapshot

# Human-readable dump (text or json)
text = panel.dump_state(format="text")
json_str = panel.dump_state(format="json")
```

### Plugin Dependencies
```yaml
# In plugin manifest
requires:
  - com.example.core  # Hard dependency - blocks if missing
optional_requires:
  - com.example.analytics  # Soft dependency - affects order only
```

### Activation Planning
```python
# Compute activation order without activating
plan = panel.activation_plan()  # -> ActivationPlan
# plan.order: activation order
# plan.blocked: plugins that can't activate (with reasons)
# plan.cycles: detected dependency cycles

# Activate all in dependency order
result = panel.activate_all()  # -> ActivationPlan
```

## Design Documents

See `docs/` for full specifications:
- `docs/design/intent.md` - Philosophy and design rationale
- `docs/design/architecture.md` - Complete architecture specification
- `docs/plans/v2-roadmap.md` - V2 roadmap and scope
- `docs/plans/backlog.md` - Deferred features
