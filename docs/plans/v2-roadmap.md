# Switchboard V2 Roadmap — Operability Release

**Status:** Draft  
**Target:** `0.2.0`  
**Baseline:** V1 complete (`0.1.0`)

---

## Goal

Make Switchboard **operable in production**: observable, debuggable, and predictable with multiple plugins.

---

## Scope

### In Scope (V2)
- Runtime introspection (`snapshot`, `dump_state`, `runtime_info`)
- Plugin dependency graph with topological activation
- Export readiness CI tests
- Documentation updates

### Out of Scope (Deferred)
See `docs/plans/backlog.md` for deferred items including:
- API levels / capability negotiation
- Configurable error strategies
- Handler signature validation
- SlotContract validation
- Terminology changes

---

## Terminology

**Decision:** Keep V1 terminology. No rename.

| Term | Meaning |
|------|---------|
| `Contribution` | What plugins provide to slots/hooks |
| `SlotContribution` | Contribution to a slot |
| `HookContribution` | Contribution to a hook |

---

## Resolution Semantics (Locked)

These behaviors are **locked for V2** and must be documented/tested.

### Slot Resolution

| Policy | Behavior | Empty Case |
|--------|----------|------------|
| `SINGLE` | Return highest priority contribution | `None` |
| `MULTI` | Return all contributions in priority order | `[]` (empty list) |

### Hook Emission

| Policy | Behavior | Empty Case |
|--------|----------|------------|
| `BROADCAST` | Call all handlers in priority order, collect results | `[]` (empty list) |
| `FIRST_RESULT` | Call handlers until first non-None returned | `None` |

---

## Hook Execution Semantics (Locked)

**Critical:** These semantics define how handlers are called and how errors are handled.

### BROADCAST (multicast)

```
for handler in handlers (priority order):
    try:
        result = handler(payload, context)
        results.append(result)
    except Exception as e:
        log error to "switchboard.hooks" logger
        continue to next handler
return results  # list, may include None values
```

- **Execution:** All handlers called, regardless of return values
- **Returns:** `list[Any]` — all results (including None)
- **Errors:** Logged and swallowed; execution continues
- **Empty:** Returns `[]`

**Error logging spec:**
- Logger name: `switchboard.hooks`
- Level: `ERROR`
- Required fields: `hook_key`, `plugin_id`, `contribution_id`, `exception type`, `exception message`
- Traceback: Yes (via `logger.exception()`)
- Test requirement: Verify exception does not stop downstream handlers and is observable in logs

### FIRST_RESULT (short-circuit)

```
for handler in handlers (priority order):
    try:
        result = handler(payload, context)
        if result is not None:
            return result
    except Exception:
        propagate immediately
return None
```

- **Execution:** Handlers called until one returns non-None (short-circuit)
- **Returns:** First non-None result, or None if all return None
- **Errors:** Propagated immediately (fail-fast)
- **Empty:** Returns `None`

**Note:** This is short-circuit semantics, not pipeline/transform. Payload is not modified between handlers.

---

## Ordering Rules (Authoritative)

**Single source of truth for deterministic ordering.**

### Uniqueness Constraints (Enforced at Registration)

| Scope | Constraint | Error on Violation |
|-------|------------|-------------------|
| `plugin_id` | Unique per PatchPanel | `DuplicateRegistrationError` |
| `contribution_id` | Unique per plugin | `DuplicateRegistrationError` |

These constraints are enforced at `register_manifest()` time. Re-registration of the same plugin_id requires explicit `unregister()` first.

### Contribution Ordering (Slots and Hooks)

Contributions are ordered by this key (applied in sequence):

1. **Priority** — descending (higher priority first)
2. **Plugin ID** — ascending (lexicographic)
3. **Contribution ID** — ascending (lexicographic)

```python
sort_key = (-contribution.priority, contribution.plugin_id, contribution.contribution_id)
```

**Immutability guarantee:** All three fields are immutable after registration. This guarantees stable ordering across restarts.

### Plugin Activation Ordering (V2)

When using `activate_all()`:

1. **Dependency order** — topological sort of `requires` graph
2. **Tie-break** — plugin_id ascending (for plugins with no dependency relationship)

---

## Lifecycle Scope (Clarification)

### What uses Transitions (V1, continuing)

- **PluginLifecycle** — `ready → starting → active → stopping → failed`

### What does NOT use Transitions (explicit non-goal)

- **Contributions** — No independent lifecycle. Contributions are active when their plugin is active.
- **PatchPanel** — No lifecycle states. Panel is ready once constructed.

This is intentional. Contributions inherit lifecycle from their owning plugin. Adding independent contribution lifecycle would create complexity without clear benefit.

---

## Deliverables

### Phase A: Introspection

**Goal:** Answer "what's wired?" in production.

#### A.1 `runtime_info()` → RuntimeInfo
```python
@dataclass(frozen=True)
class RuntimeInfo:
    framework_version: str      # e.g., "0.2.0"
    python_version: str         # e.g., "3.11.4"
    plugin_count: int
    active_plugin_count: int
    slot_count: int
    hook_count: int
```

**API:**
```python
panel.runtime_info() -> RuntimeInfo
```

**Implementation notes:**
- `framework_version`: Pull from `importlib.metadata.version("switchboard")` — always matches installed package
- `python_version`: Pull from `sys.version_info`
- Method is pure (no I/O beyond metadata read), never throws

#### A.2 `snapshot()` → RuntimeSnapshot
```python
@dataclass
class RuntimeSnapshot:
    timestamp: datetime         # Timezone-aware (UTC)
    runtime: RuntimeInfo
    plugins: list[PluginSnapshot]
    slots: list[SlotSnapshot]
    hooks: list[HookSnapshot]

# timestamp is datetime internally; serialized to ISO 8601 at dump_state() boundaries

@dataclass
class PluginSnapshot:
    plugin_id: str
    version: str
    state: str                  # Full lifecycle state (see mapping below)
    contributions: list[str]    # contribution IDs

# State values match PluginLifecycle exactly:
# ready, starting, active, stopping, failed

@dataclass  
class SlotSnapshot:
    slot_key: str
    policy: str
    contributions: list[ContributionSnapshot]

@dataclass
class HookSnapshot:
    hook_key: str
    kind: str
    policy: str
    handlers: list[ContributionSnapshot]

@dataclass
class ContributionSnapshot:
    contribution_id: str
    plugin_id: str
    priority: int
```

**API:**
```python
panel.snapshot() -> RuntimeSnapshot
```

#### A.3 `dump_state()` → str
```python
panel.dump_state(format: Literal["text", "json"] = "text") -> str
```

Human-readable text format for logs/debugging. JSON for tooling.

**Implementation notes:**
- **Determinism:** Output order is deterministic (sorted keys, stable lists) so diffs are meaningful
- **YAML:** Deferred — requires PyYAML dependency decision. Core supports text/json only.
  - Option: Add `switchboard[yaml]` extra later if needed
- **Timestamp:** Serialized to ISO 8601 string in output

#### A.4 `explain_*()` Methods (Optional)

**Status:** Nice-to-have for V2. Implement if time permits after core deliverables.

```python
panel.explain_plugin(plugin_id) -> str
panel.explain_slot(slot_key) -> str
panel.explain_hook(hook_key) -> str
```

Human-readable explanations of why something is wired the way it is:
- What's contributing, in what order, why
- What's blocked and why
- Useful for debugging "why isn't my contribution showing?"

**Decision:** `snapshot()` covers 80% of debugging needs. Add `explain_*()` if common questions arise during V2 usage.

---

### Phase B: Dependency Graph

**Goal:** Deterministic, dependency-aware activation order.

#### B.1 Manifest Additions
```python
@dataclass(frozen=True)
class PluginManifest:
    # ... existing fields ...
    requires: tuple[str, ...] = ()          # plugin IDs this depends on
    optional_requires: tuple[str, ...] = () # soft dependencies
```

**YAML:**
```yaml
requires:
  - com.example.core
  - com.example.logging
optional_requires:
  - com.example.analytics
```

**`optional_requires` behavior:**
- Affects **activation order only**, not activation eligibility
- If optional dependency is registered and activatable → activate it first
- If optional dependency is missing or blocked → proceed without it (no error)
- Cycles involving only `optional_requires` → break the cycle, log warning, proceed
- Use case: "activate analytics before me if it's there, but don't fail if it's not"

#### B.2 Activation Planning
```python
@dataclass
class ActivationPlan:
    order: list[str]            # plugin IDs in activation order
    blocked: dict[str, str]     # plugin_id -> reason
    cycles: list[list[str]]     # detected cycles

panel.activation_plan() -> ActivationPlan
panel.activate_all() -> ActivationPlan  # activates in order, returns plan
```

**Behavior:**
- Build DAG from `requires` declarations
- Topological sort with stable tie-break (plugin_id)
- Detect cycles → report, don't activate
- Missing dependency → block plugin, report reason

**Partial activation guarantees:**
- `activate_all()` activates plugins in dependency order
- If plugin N fails activation, plugins 1..(N-1) remain active
- Failed plugin is marked `failed`, dependents are marked `blocked`
- Returned `ActivationPlan` reflects final state (what succeeded, what's blocked, why)
- No rollback of successfully activated plugins on downstream failure

---

### Phase C: Export Readiness Tests

**Goal:** CI gate proving Switchboard embeds cleanly.

#### C.1 Test Cases
```
tests/test_export_readiness.py
├── test_wheel_install_and_import
├── test_sdist_install_and_import  
├── test_import_no_side_effects
├── test_public_api_surface
├── test_multi_panel_isolation
└── test_host_embedding_smoke
```

#### C.2 Host Embedding Smoke Test (pytest)
Minimal end-to-end in pytest:
1. Create PatchPanel with slots and hooks
2. Parse manifest from YAML
3. Register and activate plugin
4. Resolve slot → verify contributions
5. Emit hook → verify handler called
6. Snapshot → verify state

#### C.3 Interactive Smoke Test Script
Runnable script with visible output for manual verification:

```
examples/smoke_test.py
```

**Run with:**
```bash
python examples/smoke_test.py
```

**Output shows:**
- Step-by-step progress with ✓/✗ indicators
- Plugin registration and activation
- Slot resolution with priority ordering verification
- Hook emission with handler results
- Final pass/fail summary

**Purpose:**
- Quick sanity check during development
- Demo for new users
- Visible proof that core flow works

**CI optimization note:**
- Wheel/sdist install tests require fresh venv creation — can be slow
- Consider running these only on release branches or with `[ci full]` trigger
- Core export readiness tests (import safety, isolation, smoke) run on every PR

---

### Phase D: Documentation

- Update `docs/design/architecture.md` for V2 features
- Add introspection examples to README
- Update CLAUDE.md with new APIs

---

## Success Criteria

V2 is done when:

1. `panel.runtime_info()` returns framework metadata
2. `panel.snapshot()` returns complete runtime state
3. `panel.dump_state()` produces readable output
4. `panel.activation_plan()` computes dependency order
5. `panel.activate_all()` activates in topological order
6. Cycles and missing deps are detected and reported
7. Export readiness tests pass in CI
8. All existing V1 tests still pass
9. `ruff check .` clean
10. `mypy src` clean

---

## Implementation Order

1. Phase A.1: `runtime_info()` (simple, builds momentum)
2. Phase A.2: `snapshot()` (most valuable)
3. Phase A.3: `dump_state()` (builds on snapshot)
4. Phase B.1: Manifest `requires` field
5. Phase B.2: `activation_plan()` + `activate_all()`
6. Phase C: Export readiness tests
7. Phase D: Documentation

---

## Non-Goals (V2)

- Breaking changes to V1 API
- Terminology renames
- Async execution
- Sandboxing / isolation
- Remote plugin registries
- Contribution-level lifecycle (contributions inherit from plugin)
- PatchPanel lifecycle states (panel is stateless once constructed)
- Contract versioning separate from library versioning (deferred to backlog)
