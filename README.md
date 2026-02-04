# Switchboard

A Python-first plugin runtime providing host-owned, deterministic extensibility.

## Overview

Switchboard enables applications to define extension points (Slots and Hooks) that plugins can contribute to via declarative manifests. It provides:

- **PatchPanel**: Central registry and resolver for plugin contributions
- **Slots**: Named anchor points for UI and non-UI contributions
- **Hooks**: Named interception points for events, commands, and lifecycle
- **Deterministic resolution**: Priority-based ordering with stable tie-breaks
- **Lifecycle management**: Safe activation/deactivation with failure isolation

## Installation

```bash
pip install switchboard
```

For development:

```bash
pip install -e ".[dev]"
pre-commit install
```

## Quick Example

### Host Application Setup

```python
from switchboard import (
    PatchPanel,
    SlotDefinition,
    HookDefinition,
    SlotPolicy,
    HookKind,
    parse_manifest,
)
from switchboard.adapters.hook_router_memory import MemoryHookRouter
from switchboard.adapters.loader import ImportLoader

# Host defines extension surface
panel = PatchPanel(
    slots=[
        SlotDefinition("ui.sidebar", policy=SlotPolicy.MULTI),
        SlotDefinition("ui.main", policy=SlotPolicy.SINGLE),
    ],
    hooks=[
        HookDefinition("app.started", kind=HookKind.LIFECYCLE),
        HookDefinition("command.run", kind=HookKind.COMMAND),
    ],
    hook_router=MemoryHookRouter(),
    loader=ImportLoader(),
)
```

### Loading Plugins from YAML

```python
# Parse a plugin manifest from YAML
manifest = parse_manifest("""
manifest_version: "1"
plugin_id: com.example.myplugin
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: my_plugin:MyPlugin
contributions:
  slots:
    - contribution_id: sidebar.widget
      slot_key: ui.sidebar
      priority: 50
  hooks:
    - contribution_id: on.started
      hook_key: app.started
      handler: my_plugin:on_app_started
""")

# Register and activate
panel.register_manifest(manifest)
panel.activate("com.example.myplugin")  # Loads my_plugin:MyPlugin

# Resolve contributions (returns list of SlotContribution)
sidebar_items = panel.resolve_slot("ui.sidebar")

# Emit events (calls registered hook handlers)
results = panel.emit("app.started", payload={"timestamp": 1234567890})
```

### Plugin Implementation

```python
# my_plugin.py
class MyPlugin:
    """Plugin class instantiated on activation."""

    def activate(self, context: dict) -> None:
        print("Plugin activated!")

    def deactivate(self, context: dict) -> None:
        print("Plugin deactivated!")

def on_app_started(payload: dict, context: dict) -> str:
    return f"App started at {payload['timestamp']}"
```

## Introspection (V2)

```python
# Quick runtime overview
info = panel.runtime_info()
print(f"Plugins: {info.active_plugin_count}/{info.plugin_count}")

# Full state snapshot
snap = panel.snapshot()
for plugin in snap.plugins:
    print(f"{plugin.plugin_id}: {plugin.state}")

# Human-readable dump (for logs/debugging)
print(panel.dump_state())

# JSON dump (for tooling)
import json
data = json.loads(panel.dump_state(format="json"))
```

## Plugin Dependencies (V2)

```yaml
# In plugin manifest
requires:
  - com.example.core           # Hard dependency
optional_requires:
  - com.example.analytics      # Soft dependency (order only)
```

```python
# Activate all plugins in dependency order
result = panel.activate_all()
print(f"Activated: {result.order}")
print(f"Blocked: {result.blocked}")
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov

# Lint and format
ruff check .
ruff format .

# Type check
mypy src

# Run smoke test
PYTHONPATH=. python examples/smoke_test.py
```

## Documentation

See the `docs/` directory for detailed specifications:

- [Intent Document](docs/design/intent.md) - Philosophy and design rationale
- [Architecture Spec](docs/design/architecture.md) - Complete architecture specification
- [V2 Roadmap](docs/plans/v2-roadmap.md) - V2 features and scope

## License

MIT
