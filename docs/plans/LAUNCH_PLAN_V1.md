# Switchboard V1 Launch Plan

**Status:** Draft
**Date:** 2026-02-01

---

## Goal

Ship a minimal, working Switchboard that can be `pip install`ed and used by a host application. Prioritize correctness and clean architecture over features.

---

## V1 Non-Goals

**Do not build these in V1.** This list exists to prevent scope creep.

- **Async execution** — All emit/resolve calls are synchronous in V1
- **Marketplace/remote fetch** — No remote plugin catalogs or auto-update
- **Hot reload** — Plugins can be deactivated/reactivated, but no live code swap
- **Full sandboxing** — No subprocess isolation, containers, or capability restrictions
- **Complex type-signature enforcement** — No runtime validation of handler signatures beyond basic callable checks
- **CLI tooling** — No `switchboard list`, `switchboard doctor` commands
- **Persistence** — No JSON snapshot or registry state saving
- **Filesystem discovery** — Only explicit registration and entry points
- **UI contribution types** — No `ui.module` descriptor handling
- **Advanced failure policies** — No circuit breaker, quarantine, or per-contribution disabling
- **Plugin signing/verification** — No trust chain or signature validation

---

## V1 Public API Surface

Only symbols exported from `switchboard/__init__.py` are public/stable in V1.

### Exported Types
```python
# Core
PatchPanel
PluginManifest
SlotDefinition
HookDefinition
Contribution

# Errors
SwitchboardError
PluginNotFoundError
SlotNotFoundError
HookNotFoundError
CompatibilityError
LifecycleError
DuplicateRegistrationError
```

### PatchPanel Methods (V1)
```python
class PatchPanel:
    def __init__(self, slots: list[SlotDefinition], hooks: list[HookDefinition]) -> None: ...

    def register_manifest(self, manifest: PluginManifest) -> None: ...
    def activate(self, plugin_id: str) -> None: ...
    def deactivate(self, plugin_id: str) -> None: ...
    def resolve_slot(self, slot_key: str, context: dict | None = None) -> list[Contribution]: ...
    def emit(self, hook_key: str, payload: dict, context: dict | None = None) -> list[Any]: ...
```

### Rule
> Internal modules (`domain/`, `adapters/`, `application/`) are NOT public API. Hosts import only from `switchboard`.

---

## Manifest Schema (V1)

### Required Fields
```yaml
manifest_version: "1"           # Schema version (string)
plugin_id: "com.example.myplugin"  # Reverse-DNS style, immutable
plugin_version: "1.0.0"         # SemVer
requires_switchboard: ">=0.1,<1"   # SemVer range
entrypoint: "my_plugin:MyPlugin"   # import_path:ClassName
```

### Optional Fields
```yaml
name: "My Plugin"               # Human-readable display name
description: "Does things"      # Short description
contributions:
  slots: [...]                  # Slot contributions
  hooks: [...]                  # Hook contributions
```

### Compatibility Behavior
- `requires_switchboard` not satisfied → **hard fail** at registration (skip plugin, log error)
- Missing required field → **hard fail** at manifest parse
- Unknown fields → **ignore** (forward compatibility)

---

## Lifecycle State Invariants

Each state has invariants that MUST hold.

### `installed`
- Plugin package exists on disk / is importable
- Manifest has NOT been parsed or validated
- No state in PatchPanel

### `ready`
- Manifest parsed and validated
- `requires_switchboard` compatibility verified
- Plugin registered in PatchPanel registry
- Contributions declared but NOT active
- Entrypoint NOT yet imported

### `starting`
- Transition state (not observable externally for long)
- Entrypoint being imported
- Plugin instance being constructed
- Contributions being registered with router
- **On failure**: rollback to `ready`, store error, optionally transition to `failed`

### `active`
- Plugin instance exists and `activate()` was called
- All contributions registered and resolvable
- Hook handlers wired and invocable
- Plugin can receive `emit()` calls

### `stopping`
- Transition state
- `deactivate()` called on plugin instance
- Contributions being unregistered
- Hook handlers being unwired
- **On completion**: return to `ready`

### `failed`
- Plugin is quarantined
- `last_error` stored (exception + traceback digest)
- Contributions NOT resolvable
- Hook handlers NOT invocable
- Can transition to `ready` via explicit reset (V1: requires re-registration)

---

## resolve_slot() Semantics

### Return Type
`resolve_slot(slot_key, context) -> list[Contribution]`

Returns `Contribution` objects, NOT callables or instances. The host invokes contributions.

### Contribution Fields
```python
@dataclass
class Contribution:  # Base class
    plugin_id: str          # Owning plugin
    contribution_id: str    # Unique within plugin
    priority: int           # Higher = first (default 50)
    metadata: dict          # Plugin-provided metadata

class SlotContribution(Contribution):
    slot_key: str           # Target slot
    factory: str            # Import path to callable

class HookContribution(Contribution):
    hook_key: str           # Target hook
    handler: str            # Import path to callable
```

### Ordering Rules
1. Higher `priority` first
2. Tie-break: `plugin_id` ascending (lexicographic)
3. Tie-break: `contribution_id` ascending (lexicographic)

### Policy Enforcement
- `policy="multi"` (default): Return all matching contributions
- `policy="single"`: Return only highest-priority contribution (as single-item list)

---

## Hook Dispatch Semantics (V1)

### Supported Policies
Only two policies in V1:

1. **`broadcast`** (default for `kind="event"` and `kind="lifecycle"`)
   - Call ALL registered handlers in priority order
   - Collect all return values into a list
   - Continue even if a handler raises (log error, continue)

2. **`first_result`** (default for `kind="command"`)
   - Call handlers in priority order
   - Return first non-`None` result
   - If all return `None`, return `None`
   - Stop on first non-`None` (short-circuit)

### Ordering Rules
Same as slot resolution:
1. Higher `priority` first
2. Tie-break: `plugin_id` ascending
3. Tie-break: `contribution_id` ascending

### Edge Cases
- No handlers registered → return `[]` (broadcast) or `None` (first_result)
- Handler raises exception → log error, continue to next (broadcast) or propagate (first_result)

---

## Architecture: Registry vs Execution

PatchPanel is **registry + resolution only**. Execution is delegated to ports.

```
┌─────────────────────────────────────────────────────┐
│                    PatchPanel                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Plugins   │  │    Slots    │  │    Hooks    │  │
│  │  (registry) │  │  (registry) │  │  (registry) │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                         │                │           │
│                    resolve()          emit()        │
│                         │                │           │
│                         ▼                ▼           │
│              ┌─────────────────────────────┐        │
│              │      HookRouterPort         │◄── Port │
│              └─────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────────┐
              │   PluggyHookRouterAdapter   │◄── Adapter
              └─────────────────────────────┘
```

**Rule**: No Pluggy imports in `domain/`. Pluggy lives in `adapters/` only.

---

## Concurrency Contract (V1)

### Thread Safety
- `register_manifest()`, `activate()`, `deactivate()` acquire an exclusive lock
- `resolve_slot()`, `emit()` acquire a shared lock
- Calling `emit()` or `resolve_slot()` during `activate()` from another thread will block

### Forbidden
- Calling `register_manifest()` from within a hook handler → raises `LifecycleError`
- Calling `activate()` from within a hook handler → raises `LifecycleError`

### Test Requirement ✓
Added `tests/test_concurrency.py` with:
- Re-entrancy protection tests (register/activate/deactivate from hook handler)
- Thread safety tests (concurrent resolve, emit during activate)

---

## Phase 1: Project Scaffolding ✓

### 1.1 Package Configuration
- [x] `pyproject.toml` with full config
- [x] `src/switchboard/__init__.py` with version
- [x] `.gitignore`

### 1.2 GitHub Essentials
- [x] `README.md`
- [x] `LICENSE` (MIT)
- [x] `.github/workflows/ci.yml`

### 1.3 Development Setup
- [x] `.pre-commit-config.yaml`
- [x] `tests/` directory

---

## Phase 2: Domain Layer ✓

### 2.1 Value Objects (`domain/models.py`)
- [x] `SemVer` (parse, compare, match range)
- [x] `ApiRange` (parse range string, check compatibility)

### 2.2 Entities (`domain/models.py`)
- [x] `PluginManifest` (frozen dataclass)
- [x] `SlotDefinition` (slot_key, policy, description)
- [x] `HookDefinition` (hook_key, kind, policy)
- [x] `SlotContribution`, `HookContribution`

### 2.3 Lifecycle State Machine (`domain/lifecycle.py`)
- [x] `PluginLifecycle` using Transitions library
- [x] States: `ready`, `starting`, `active`, `stopping`, `failed`
- [x] Transitions:
  - `ready → starting → active` (activation flow)
  - `active → stopping → ready` (deactivation flow)
  - `starting → ready` (rollback on activation failure)
  - `starting/active → failed` (fatal error)
  - `failed → ready` (manual reset)
- [x] Guarded transitions with `LifecycleError` on invalid state
- [x] `last_error` storage for `failed` state
- [x] `rollback()` cleans up partial registrations on activation failure

**Note:** `installed` state deferred - V1 uses explicit `register_manifest()` which
validates and creates lifecycle in `ready` state. `installed` would only be needed
for filesystem discovery (V2+).

### 2.4 Errors (`domain/errors.py`)
- [x] Exception hierarchy as specified in Public API

### 2.5 Ports (`domain/ports.py`)
- [x] `HookRouterPort` protocol (register_handler, emit)
- [x] `LoaderPort` protocol (load_entrypoint)

### 2.6 PatchPanel Core (`domain/patch_panel.py`)
- [x] Slot/Hook storage and lookup
- [x] Plugin registry (manifest → lifecycle)
- [x] `register_manifest()` with validation
- [x] `resolve_slot()` with ordering and policy
- [x] Thread safety (RLock)
- [x] Delegate `emit()` to HookRouterPort
- [x] Rollback of partial registrations on activation failure

---

## Phase 3: Host Use Case Validation ✓

**Before Pluggy integration**, validate the host-facing API works.

### 3.1 In-Memory Hook Router (`adapters/hook_router_memory.py`)
- [x] Simple `MemoryHookRouter` implementing `HookRouterPort`
- [x] Stores handlers in a dict
- [x] Implements `broadcast` and `first_result` policies
- [x] No Pluggy dependency

### 3.2 Simple Loader (`adapters/loader.py`)
- [x] `ImportLoader` implementing `LoaderPort`
- [x] Import entrypoint string, instantiate class

### 3.3 Golden Path Test
- [x] Test matching README example
- [x] Register manifest → activate → resolve_slot → emit
- [x] Verify ordering, policy enforcement

---

## Phase 4: Pluggy Integration ✓

Now swap in Pluggy behind the port.

### 4.1 Pluggy Adapter (`adapters/hook_router_pluggy.py`)
- [x] `PluggyHookRouter` implementing `HookRouterPort`
- [x] Dynamic hookspec generation with `firstresult=True`
- [x] Handler registration with priority via LIFO ordering
- [x] `first_result`: Pluggy dispatch via `pm.hook.method()` (stops on first non-None)
- [x] `broadcast`: Manual iteration for continue-on-error semantics

**Design:** Pluggy handles `first_result` dispatch (semantics match exactly).
Broadcast uses manual iteration because Pluggy propagates exceptions and we want
continue-on-error for lifecycle/event hooks.

### 4.2 Integration Test
- [x] Same golden path test passes with Pluggy adapter (`test_golden_path_both_routers.py`)
- [x] Verify no Pluggy types leak into domain (`TestPluggyNoLeakage`)

---

## Phase 5: Application Layer ✓

Thin orchestration over domain.

### 5.1 Manifest Parsing (`application/manifest.py`)
- [x] `parse_manifest(yaml_str) -> PluginManifest`
- [x] `load_manifest(path) -> PluginManifest`
- [x] Validation via dataclass `__post_init__` and parsing logic
- [x] Unknown fields ignored (forward compatibility)
- [x] Exported from main `switchboard` package

### 5.2 JSON Schema
- [ ] Optional: JSON Schema for V1 manifest format (deferred - dataclass validation sufficient for V1)

---

## Phase 6: Testing & Documentation ✓

### 6.1 Unit Tests
- [x] SemVer parsing and range matching (`test_models.py` - 35 tests)
- [x] Lifecycle transitions (`test_lifecycle.py` - 14 tests)
- [x] PatchPanel registration and resolution (`test_patch_panel.py` - 28 tests)
- [x] Hook routing both policies (`test_hook_router_pluggy.py`, `test_adapters.py`)
- [x] Concurrency (`test_concurrency.py` - 5 tests)
- [x] Manifest parsing (`test_manifest_parsing.py` - 20 tests)

### 6.2 Integration Tests
- [x] Golden path (`test_golden_path.py`, `test_golden_path_both_routers.py`)
- [x] Failure scenarios (bad manifest, missing slot, lifecycle violations)
- [x] Multiple plugins with priority ordering
- [x] Rollback on activation failure

### 6.3 Documentation
- [x] README updated with YAML parsing example
- [x] Docstrings on all public API
- [x] CLAUDE.md updated

---

## Success Criteria

V1 is "done" when:

1. `pip install -e .` works
2. README example executes without modification
3. Golden path test passes
4. All unit/integration tests pass
5. `ruff check .` clean
6. `mypy src` clean
7. Concurrency test exists and passes

---

## Implementation Order

1. ~~Phase 1~~ ✓
2. Phase 2.4 errors (needed by everything)
3. Phase 2.1-2.2 models (value objects, entities)
4. Phase 2.5 ports (define interfaces)
5. Phase 2.3 lifecycle (Transitions integration)
6. Phase 2.6 PatchPanel core
7. Phase 3.1-3.2 memory router + loader (simple adapters)
8. Phase 3.3 golden path test (validate host API)
9. Phase 4 Pluggy integration (swap adapter)
10. Phase 5 manifest parsing
11. Phase 6 remaining tests + docs

---

## Decisions

1. **License:** MIT
2. **Python version:** 3.11+
3. **Manifest format:** YAML primary
4. **resolve_slot returns:** `list[Contribution]` (not callables)
5. **V1 hook policies:** `broadcast` and `first_result` only
6. **Concurrency model:** Exclusive lock for mutations, shared for reads
