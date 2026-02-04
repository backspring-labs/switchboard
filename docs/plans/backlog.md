# Switchboard Backlog — Deferred Features

**Status:** Parking lot for features not in current roadmap  
**Last updated:** 2026-02-03

---

## Overview

These features were considered for V2 but deferred. They may be picked up in future releases based on real-world need.

---

## Deferred Items

### 1. API Levels & Capability Negotiation

**Source:** v2-spec.md §5

**Concept:**
- `switchboard_api_level: int` for compatibility checking
- `capabilities_required: list[str]` in manifests
- `capabilities_provided: list[str]` from host

**Why deferred:**
- Over-engineering for alpha stage
- SemVer + `requires_switchboard` range is sufficient for now
- Add when we have breaking changes to manage across many plugins

---

### 2. Configurable Hook Error Strategies

**Source:** v2-spec.md §6.1

**Concept:**
```python
class ErrorStrategy(Enum):
    RAISE_FIRST = "raise_first"
    LOG_AND_CONTINUE = "log_and_continue"
    COLLECT_ERRORS = "collect_errors"
    FAIL_AFTER = "fail_after"
```

Per-hook configuration:
```python
HookDefinition("app.started", error_strategy=ErrorStrategy.LOG_AND_CONTINUE)
```

**Why deferred:**
- Current defaults are sensible (propagate for FIRST_RESULT, continue for BROADCAST)
- Adds complexity to HookDefinition
- No concrete need yet

---

### 3. EmissionResult / emit_full()

**Source:** v2-spec.md §6.1

**Concept:**
```python
@dataclass
class EmissionResult:
    results: list[Any]
    errors: list[HandlerError]
    strategy: ErrorStrategy
    duration_ms: float
    handler_count: int

panel.emit_full(hook_key, payload) -> EmissionResult
```

**Why deferred:**
- Current `emit()` return value is sufficient
- Add when structured error collection is actually needed
- Can be added without breaking existing `emit()`

---

### 4. Handler Signature Validation

**Source:** v2-spec.md §6.6

**Concept:**
```python
@dataclass
class SignatureSpec:
    required_args: tuple[str, ...]
    optional_args: tuple[str, ...]
    return_type: type | None

HookDefinition("cmd.run", signature=SignatureSpec(required_args=("payload", "context")))
```

Validation at registration time, not emit time.

**Why deferred:**
- Adds complexity to registration path
- Current fail-at-emit is acceptable for most cases
- Type hints are not enforced at runtime in Python anyway

---

### 5. SlotContract Validation

**Source:** v2-spec.md §6.5, v2-addendum-svelte-ui.md §5

**Concept:**
```python
@dataclass
class SlotContract:
    required_fields: tuple[str, ...]
    schema: dict | None  # JSON Schema

SlotDefinition("ui.sidebar", contract=SlotContract(required_fields=("component_key",)))
```

**Why deferred:**
- Only needed for complex UI descriptor patterns
- Continuum-specific need, not core Switchboard
- YAGNI until UI slot contributions are actually built

---

### 6. Manifest Pre-Validation API

**Source:** v2-spec.md §6.5

**Concept:**
```python
panel.validate_manifest(manifest) -> ValidationReport
```

Validate before registration:
- Referenced slots/hooks exist
- Dependencies resolve
- Compatibility checks pass

**Why deferred:**
- V1 already validates at `register_manifest()` time
- Marginal improvement to fail slightly earlier
- Consider adding if manifest loading becomes async/batch

---

### 7. explain_*() Methods

**Source:** v2-spec.md §6.4

**Concept:**
```python
panel.explain_plugin(plugin_id) -> Explanation
panel.explain_slot(slot_key) -> Explanation
panel.explain_hook(hook_key) -> Explanation
```

Detailed explanations of why something is wired the way it is.

**Why deferred:**
- `snapshot()` covers 80% of debugging needs
- Add if "why is this not showing?" questions become frequent
- Lower priority than core introspection

---

### 8. Terminology Rename (Contribution → Patch)

**Source:** v2-spec.md §4

**Concept:**
Rename for consistency with "PatchPanel":
- `Contribution` → `Patch`
- `SlotContribution` → `SlotPatch`
- `HookContribution` → `HookPatch`

**Decision: Not doing this.**

Reasons:
- Already implemented with "Contribution"
- "Patch" is overloaded (bug fix, security patch)
- Rename is pure churn with no functional benefit
- "PatchPanel" name works fine with "Contribution"

---

### 9. Async Router / emit_async()

**Source:** v2-spec.md §8

**Concept:**
- `AsyncRouterPort` protocol
- `panel.emit_async(hook_key, payload)` for async handlers
- Capability flag: `switchboard.async_router`

**Why deferred:**
- V2 explicitly keeps sync-first
- Adds significant complexity (cancellation, timeouts, concurrency)
- Add when there's a concrete async use case

---

### 10. Svelte UI Component Loading

**Source:** v2-addendum-svelte-ui.md §10

**Concept:**
Plugins ship actual Svelte components (not just descriptors):
- `module_ref` in manifest
- Dynamic import in Continuum
- Trust/signing model

**Why deferred:**
- Descriptor pattern is safer and simpler
- Requires Continuum bundling infrastructure
- Security implications need careful design
- Explicitly marked as 0.3+ / 1.0 scope

---

### 11. Contract Versioning (Separate from Library SemVer)

**Source:** V2 plan feedback

**Concept:**
Separate versioning for:
- **Library version** — Switchboard package SemVer (`0.2.0`)
- **Contract version** — Slot/Hook schema version (major breaks compat, minor adds fields)

Plugins would declare compatible contract version range:
```yaml
contract_version: ">=1.0,<2.0"
```

**Why deferred:**
- Related to API levels (also deferred)
- Adds manifest complexity
- No concrete need until we have breaking slot/hook schema changes
- Library SemVer + `requires_switchboard` is sufficient for now

**When to reconsider:**
- When slot/hook contracts need independent evolution from library version
- When host needs to support plugins targeting different contract versions

---

## Picking Up Deferred Items

When considering a deferred item:

1. **Validate the need** - Is there a concrete use case, or is it speculative?
2. **Check dependencies** - Does it require other deferred items?
3. **Assess complexity** - Is the implementation cost justified?
4. **Consider alternatives** - Can the need be met with existing features?

If the answer is "yes, we need this now," move it to the active roadmap with a clear scope.
