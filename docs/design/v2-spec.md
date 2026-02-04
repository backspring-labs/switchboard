# Switchboard — V2 Design Spec (Recommended Enhancements)

**Doc status:** Draft (rewrite aligned to Intent + V1 Spec + Slot/Hook/PatchPanel vocabulary)  
**Target line:** `0.2.x` (still Alpha)  
**Baseline:** `0.1.0-alpha` (V1 feature set complete)

---

## 0. Executive Summary

V1 demonstrates a strong foundation: a **host-owned**, **deterministic** plugin runtime with a clean **DDD + Hex** structure, clear lifecycle states, and solid testing. The external feedback and internal intent both converge on the same next step:

> **V2 should make Switchboard “operable in anger”**: predictable failure behavior, safer integration (validation), deterministic activation order (dependencies), and first-class introspection/diagnostics—while preserving the host-owned posture and not ballooning into a sandbox or marketplace.

V2 introduces a cohesive capability set we’ll refer to as the **Deterministic Operability Layer**:
- dependency-aware activation plans
- runtime snapshot + explain/dump tools
- manifest pre-validation against host-defined Slots/Hooks
- handler signature validation at registration-time
- clearer and optionally configurable hook error strategies
- testing harness utilities for plugin authors and host teams
- **framework versioning + capability negotiation** as a standard practice for evolution

---

## 1. Background & Intent (V2 framing)

Switchboard exists to prevent “plugin drift”: scattered registries, import side-effects, inconsistent lifecycle, and no way to explain what’s wired in prod. The host defines seams intentionally.

In V2, we keep the “host-owned seam” philosophy, using the aligned vocabulary:

- **Slot**: a host-defined attachment target (often UI anchors, but not limited to UI).
- **Hook**: a host-defined interception pipeline (events, before/after/around, command interception).
- **PatchPanel**: the registry/resolver/invoker that holds Slot/Hook declarations and plugin patches.
- **Patch**: what plugins contribute to Slots/Hooks (typed as SlotPatch / HookPatch where helpful).

V2 emphasizes that **Slot/Hook are still host-declared seams**—not “inject anywhere.”

---

## 2. Goals

### 2.1 Functional goals (V2)
1. **Predictable hook failure semantics**: documented and optionally configurable per Hook.
2. **Dependency-aware activation**: plugins declare dependencies; PatchPanel produces deterministic activation plans.
3. **Introspection & diagnostics**: snapshot, dump, explain (for plugins, slots, hooks, patches).
4. **Manifest pre-validation**: validate manifests against host-declared Slots/Hooks before runtime registration failures.
5. **Handler signature validation**: fail early at registration, not at emit-time.
6. **Testing utilities**: easy plugin-in-isolation harness (fake host, in-memory loader/router, snapshot assertions).
7. **Framework versioning**: formalize compatibility and capability negotiation as first-class, standard practice.

### 2.2 Quality goals (V2)
- Determinism remains a contract (stable ordering + stable tie-breakers).
- Maintain DDD/Hex boundaries (domain stays small; adapters carry plumbing).
- Preserve V1 behavior by default; new strictness is opt-in.
- Great ergonomics for both host integrators and plugin authors.

---

## 3. Non-Goals (V2)
- Sandboxing / process isolation / permissioning / secure enclaves.
- Remote plugin registries, auto-update, marketplace UX.
- Mandatory async-first redesign of core APIs (V2 may add an async adapter path, but not force a breaking rewrite).

---

## 4. Terminology (Aligned)

| Term | Meaning |
|---|---|
| **Switchboard** | The project + Python package name (`switchboard`) |
| **PatchPanel** | Core registry/resolution engine (`from switchboard import PatchPanel`) |
| **Slot** | Host-declared attachment target (often UI anchors; has cardinality) |
| **Hook** | Host-declared interception pipeline / event dispatch |
| **Patch** | Plugin-provided contribution registered to a Slot or Hook |
| **SlotPatch** | Patch intended for Slot resolution/rendering |
| **HookPatch** | Patch intended for Hook emission/interception |
| **Plugin Manifest** | Plugin metadata + declarations (patches, deps, compat) |
| **Contract** | Host-defined shape/constraints for Slot/Hook contributions |

---

## 5. Framework Versioning & Compatibility (New Standard Practice)

V1 appropriately labels `0.1.0` as Alpha. V2 formalizes evolution so hosts can scale plugins safely.

### 5.1 Switchboard SemVer discipline in `0.x`
- Continue SemVer.
- Acknowledge `0.MINOR` may include breaking changes; document them.
- `0.PATCH` remains bugfix-only.

### 5.2 API levels (host-facing stability primitive)
Introduce a numeric API level to avoid premature complexity with version ranges:

- **Switchboard API level**: `switchboard_api_level: int` exposed by PatchPanel runtime.
- **Host API level**: `host_api_level: int` declared by the host using Switchboard.
- **Plugin required host API level**: `plugin_requires_host_api_level: int` in plugin manifest.

**Rule:** plugin is eligible iff `host_api_level >= plugin_requires_host_api_level`.

### 5.3 Capability negotiation (feature detection)
Add a small canonical capability namespace, returned by PatchPanel:

- `switchboard.dep_graph`
- `switchboard.introspection`
- `switchboard.manifest_validation`
- `switchboard.signature_validation`
- `switchboard.hook_error_strategies`
- `switchboard.testing_harness`
- `switchboard.async_router` (future)

Plugin manifests may include `capabilities_required: list[str]`.

**Rule:** plugin is eligible iff `capabilities_required ⊆ host_capabilities_provided`.

### 5.4 Runtime info API
Add a stable method:

- `panel.runtime_info() -> RuntimeInfo`
  - `framework_version`
  - `switchboard_api_level`
  - `capabilities`

---

## 6. V2 Capability Set (Recommended)

### 6.1 Hook failure semantics: document + configure

#### V2 deliverables
- **Docs**: Explicitly describe default behaviors for Hook emission policies.
- **Optional configuration**: per Hook error strategy (host-defined).

#### ErrorStrategy (Value Object)
Recommended strategies:
- `RAISE_FIRST` — fail fast on first exception
- `LOG_AND_CONTINUE` — log and continue (common for broadcast)
- `COLLECT_ERRORS` — return results + errors (no raise)
- `FAIL_AFTER` — run all handlers; raise an aggregate error at end
- `CUSTOM(callable)` — advanced host-controlled behavior

#### EmissionResult (data structure)
- `results: list[Any]`
- `errors: list[HandlerError]`
- `strategy: ErrorStrategy`
- optional telemetry fields (`duration_ms`, `handler_count`)

#### API shape (non-breaking)
- Keep V1 default return behavior.
- Add `emit_full(hook_id, payload) -> EmissionResult` as the consistent “always returns details” path.

---

### 6.2 Contribution metadata conventions (typed + documented)

V1’s `metadata: dict` is powerful but undefined. V2 standardizes conventions without removing flexibility.

#### Reserved metadata keys (TypedDict recommended)
`PatchMetadata` (names reserved by Switchboard; optional):
- `id: str` (stable patch id)
- `tags: list[str]`
- `roles: list[str]` (host-defined)
- `feature_flags: dict[str, bool]`
- `ui: dict[str, Any]` (optional; host-defined UI hints)
- `custom: dict[str, Any]` (plugin-owned escape hatch)

**Rule:** Switchboard only interprets reserved top-level keys; everything else is opaque.

Docs include:
- how to do role filtering deterministically
- how to do feature-flag gating
- how UI hints should stay host-defined and non-core

---

### 6.3 Plugin dependency graph + deterministic activation

#### Manifest additions
- `requires: list[PluginRef]`
- `optional_requires: list[PluginRef]`

`PluginRef`:
- `id: str`
- optional `reason: str`
- optional `version_constraint: str` (defer strict enforcement unless you want it now)

#### Behavior
- PatchPanel builds dependency DAG.
- `activate_all()` produces a **topological activation plan** with a stable tie-breaker.
- Cycle detection produces an actionable diagnostic.

#### Diagnostics
Add activation outcomes/reasons:
- `BLOCKED_BY_DEPENDENCY`
- `INCOMPATIBLE` (api_level/capabilities mismatch)

---

### 6.4 Introspection & diagnostics (first-class)

V2 adds stable runtime introspection primitives.

#### RuntimeSnapshot
A JSON-serializable snapshot including:
- runtime info (version, api_level, capabilities)
- Slots (definitions, cardinality, contracts, resolved patches)
- Hooks (definitions, strategies, signatures, registered handlers)
- Plugins (states, compat, deps, errors)
- Patches (by plugin, by target, ordering)
- recent errors/events (bounded history)

#### APIs
- `panel.snapshot() -> RuntimeSnapshot`
- `panel.dump_state(format="text|json|yaml") -> str`
- `panel.explain_plugin(plugin_id) -> Explanation`
- `panel.explain_slot(slot_id) -> Explanation`
- `panel.explain_hook(hook_id) -> Explanation`

**Guideline:** default redaction of payloads/contexts in dumps (safe for logs).

---

### 6.5 Manifest pre-validation (against host-declared Slots/Hooks)

V2 adds a validation step before registration/activation.

Validation checks:
- referenced Slot/Hook IDs exist
- patch kind matches target kind (SlotPatch → Slot, HookPatch → Hook)
- required contract fields exist (if contract schema present)
- dependency references resolve (if known set of plugins)
- compat checks pass (api_level/capabilities) *as early as possible*

#### APIs
- `panel.validate_manifest(manifest) -> ValidationReport`
- `load_plugin(..., validate=True)` (recommended default True in v2)

Optional CLI:
- `python -m switchboard.validate path/to/plugin`

---

### 6.6 Handler signature validation (registration-time)

V1 can surface handler mismatch at emit-time. V2 supports opt-in early failure.

Host declares expected signature per Hook (and optionally Slot render callables if used):
- minimal: `inspect.Signature` shape
- pragmatic: a `SignatureSpec` object:
  - required args
  - optional args
  - return expectation category (void/single/multi)

Validation rules:
- handler is callable
- arity and required parameters compatible
- type hints validation is best-effort only (do not overpromise)

#### APIs
- `declare_hook(hook_id, signature=SignatureSpec(...), validate_handlers=True)`
- `register_hook_patch(..., validate=True|False)` (inherits defaults)

---

### 6.7 Testing utilities (switchboard.testing)

Provide a `switchboard.testing` module that makes plugin authoring and host testing easier.

Recommended utilities:
- `FakeHost` / `TestPanel` for declaring Slots/Hooks + loading manifests from memory
- `InMemoryLoader`
- `InMemoryRouter` with deterministic capture
- `capture_emissions()` context manager
- `assert_snapshot_matches(snapshot, golden_path)` helper

This supports “belt & suspenders” smoke tests: load → validate → activate → emit → snapshot.

---

## 7. Adapter Guidance (Docs)

V2 docs should include a clear “choose your adapter” guide:

- **InMemoryRouter**: tests; deterministic; supports emission capture.
- **PluggyRouter**: production default; mature dispatch.
- **AsyncRouter (future)**: long-running handlers/cancellation/concurrency; behind a capability gate.

Also include recipes:
- custom loaders (entry points, filesystem, explicit registry)
- custom routers (wrapping pluggy for telemetry)
- filtering/gating using metadata (roles/tags/feature flags)

---

## 8. Async / Long-running Hooks (Roadmap Bridge)

V2 should not force breaking changes. Provide a bridge design:

- Define an optional `AsyncRouterPort` and capability `switchboard.async_router`.
- Add:
  - `emit_async(hook_id, payload)` only if router supports it, or
  - separate `AsyncPatchPanel` wrapper (keeps core stable)

Docs should include:
- guidance for long-running handlers (timeouts, cancellation tokens, queueing strategies)
- recommendation to keep core deterministic: async concurrency decisions are adapter policy.

---

## 9. DDD + Hex (V2 adjustments)

V2 keeps the bounded context small and focused:

### Domain
- **PatchPanel** (Aggregate Root)
- **SlotDefinition** (Entity) — cardinality, contract, resolution rules
- **HookDefinition** (Entity) — strategy, signature spec, ordering rules
- **PluginPackage / PluginInstance** (Entities) — manifest, lifecycle, compat
- **Patch** (Entity) — target id, handler/ref, metadata

### Value objects
- `ErrorStrategy`
- `SignatureSpec`
- `PluginRef`
- `ValidationReport`
- `RuntimeInfo`
- `RuntimeSnapshot`

### Application services
- `LoadPlugin`
- `ValidateManifest`
- `PlanActivation`
- `ActivatePlugins`
- `EmitHook` / `ResolveSlot`
- `SnapshotRuntime`

### Adapters
- loaders, routers, storage, logging/telemetry

---

## 10. Backwards Compatibility & Migration

### 10.1 Compatibility stance
- V2 defaults preserve V1 behavior.
- New strictness is opt-in via:
  - host declarations (contracts, signatures, error strategies)
  - enabling manifest validation
  - enabling handler validation

### 10.2 Recommended migration order
1. Upgrade to `0.2.x` with defaults → behavior matches V1.
2. Add `snapshot()` + `dump_state()` to improve observability immediately.
3. Publish metadata conventions guide; optionally add linting in plugin repos.
4. Enable manifest pre-validation in host.
5. Add dependency declarations; switch host activation to `activate_all()` planning.
6. Turn on handler signature validation per Hook once ecosystem is cleaned up.
7. Optionally adopt hook error strategy configuration where it matters most.

---

## 11. Definition of Done (V2 deliverables)

### Must ship
- Docs:
  - hook error-handling policy (explicit)
  - adapter selection guide
  - metadata conventions guide
- Runtime:
  - `runtime_info()`
  - `snapshot()` + `dump_state()`
  - dependency graph + activation planning
  - manifest validation against host-declared Slots/Hooks
  - handler signature validation (opt-in)
- Testing:
  - `switchboard.testing` minimal harness

### Nice-to-have
- per-Hook configurable error strategies
- validation CLI entrypoint
- `activation_plan()` report object suitable for CI artifacts

### Deferred (explicit)
- sandboxing/isolation
- remote registries/auto-update
- breaking async-first core

---

## Appendix A: Minimal API additions (illustrative)

- `PatchPanel.runtime_info() -> RuntimeInfo`
- `PatchPanel.snapshot() -> RuntimeSnapshot`
- `PatchPanel.dump_state(format="text") -> str`
- `PatchPanel.validate_manifest(manifest) -> ValidationReport`
- `PatchPanel.activation_plan() -> ActivationPlan`
- `PatchPanel.emit_full(hook_id, payload) -> EmissionResult`
- `PatchPanel.declare_slot(slot_id, *, cardinality, contract=None, ...)`
- `PatchPanel.declare_hook(hook_id, *, signature=None, error_strategy=None, ...)`

---

## Appendix B: Example manifest (illustrative)

```yaml
id: "com.example.pluginA"
name: "Plugin A"
version: "0.3.0"

plugin_requires_host_api_level: 1
capabilities_required:
  - "switchboard.introspection"
  - "switchboard.manifest_validation"

requires:
  - id: "com.example.core"
    reason: "Consumes core domain events"

patches:
  - kind: "slot"
    slot_id: "ui.slot.left_nav"
    handler: "plugin_a.nav:nav_items"
    metadata:
      id: "pluginA.leftnav"
      tags: ["ui", "nav"]
      roles: ["admin"]
      ui:
        title: "Plugin A"
        icon: "spark"
      custom:
        any_plugin_specific_field: true

  - kind: "hook"
    hook_id: "app.starting"
    handler: "plugin_a.lifecycle:on_starting"
    metadata:
      id: "pluginA.on_starting"
      tags: ["lifecycle"]
```

---

## Appendix C: The V2 “headline capability”

**Deterministic Operability Layer**  
The set of features that make Switchboard predictable, diagnosable, and safe under real usage:
- dependency-aware activation plans
- runtime snapshot + explain + dump
- manifest + signature validation
- hook error strategy clarity/configurability
