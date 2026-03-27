# Plan: TypeScript Port of Switchboard (`@switchboard/core`)

## Context

Switchboard is a Python plugin runtime library providing host-owned, deterministic extensibility. The idea doc (`guiderail/docs/ideas/switchboard-plugin-model-idea.md`) proposes a TypeScript port as Phase 1 of making Switchboard polyglot — enabling GuideRail (a React app) to use the same plugin architecture. This is the `@switchboard/core` package only; GuideRail integration is a separate future phase.

The TypeScript implementation must preserve the Python runtime's behavioral contract: manifest meaning, dependency resolution, lifecycle semantics, slot/hook resolution, activation planning, and runtime introspection must behave equivalently. The implementation may be TypeScript-idiomatic in naming, typing, packaging, and internal structure, but must not change the runtime model or observable semantics.

---

## Compatibility Contract

### Must be identical to Python
- Manifest field names and manifest meaning
- Dependency resolution semantics (Kahn's algorithm, hard vs soft deps)
- Lifecycle state semantics and transition validity
- Slot resolution semantics (priority ordering, MULTI/SINGLE policies)
- Hook dispatch semantics (BROADCAST, FIRST_RESULT, priority ordering, failure isolation)
- Activation planning semantics (order, blocked, cycles)
- Runtime snapshot / introspection semantics
- Error conditions and error trigger points
- Deterministic tie-breaking: priority (desc) → plugin_id (asc) → contribution_id (asc)

### May differ from Python
- Public naming style (`camelCase`)
- Internal implementation strategy (no Pluggy, no Transitions)
- Loader implementation details (registration-based vs importlib)
- Packaging/build tooling
- `null`/`undefined` handling (see Nullability Policy below)

---

## Async Boundary (v0.2.0)

Phase 1 is **synchronous-only**:
- Plugin factories are synchronous
- Activation/deactivation is synchronous
- Hook handlers are synchronous
- `emit()` and `resolveSlot()` are synchronous

Async support, if needed later, will be introduced as explicit parallel APIs (e.g., `emitAsync`, `activateAsync`) rather than silently changing current method signatures.

---

## Nullability Policy

- **`undefined`**: used for omitted input fields and optional TypeScript object properties (idiomatic TS)
- **`null`**: used only for intentional explicit absence in runtime return values (e.g., `emit()` with FIRST_RESULT returning `null` when no handler matches)
- Public APIs must not mix both in the same return position
- Snapshot types use `undefined` for optional fields, never `null`

---

## Normalization Rules

- Identifiers (plugin IDs, slot keys, hook keys, contribution IDs) are **case-sensitive**
- Manifest lists preserve declared order unless runtime sorting is part of semantics (e.g., resolution ordering)
- Unknown manifest fields are **ignored** (forward compatibility)
- Default hook/slot policy derivation must match Python exactly (`EVENT`→`BROADCAST`, `COMMAND`→`FIRST_RESULT`, `LIFECYCLE`→`BROADCAST`)
- SemVer parsing must match Python edge-case behavior or explicitly document differences

---

## Re-entrancy Guard

A boolean flag prevents mutating nested execution that would compromise deterministic state transitions:
- **Guarded operations**: `activate`, `deactivate`, `activateAll`, `registerManifest`, `unregister`
- **Allowed during guarded execution**: read-only methods (`resolveSlot`, `emit`, `snapshot`, `runtimeInfo`, `activationPlan`, `dumpState`, `getPluginState`, `listPlugins`)
- **Error thrown**: `LifecycleError` with a clear message indicating re-entrant mutation was rejected
- **Nested `emit()`**: allowed (read-only dispatch)
- **Activation during activation**: rejected

---

## Non-Goals for Phase 1

- GuideRail host integration
- Dynamic module discovery/import scanning
- Async plugin lifecycle
- Remote plugin loading
- Browser sandboxing/security isolation
- Hot reload
- Plugin marketplace/distribution
- Multi-package TS ecosystem beyond `@switchboard/core`
- npm publishing automation

---

## Key Design Decisions

1. **Repo structure**: Restructure into a monorepo with `packages/switchboard-python/` and `packages/switchboard-typescript/` side by side. Python package internals unchanged — same `import switchboard` path, same wheel output. Add `pnpm-workspace.yaml` at root for the TS workspace.
2. **Zero runtime dependencies**: Hand-roll hook dispatch (~300 lines) and lifecycle state machine (~50 lines). No Pluggy, no Transitions, no XState.
3. **Manifest format**: JSON is canonical. `parseManifest(data)` accepts a plain object. YAML support is **out of scope for core** — a future helper package or the consuming host can parse YAML and pass the resulting object to `parseManifest`.
4. **LoaderPort**: Registration-based `RegistryLoader` (not dynamic imports). Hosts register plugin factories by key. TypeScript-idiomatic for browser+Node.
5. **Sync-only**: All APIs are synchronous in v0.2.0.
6. **Build toolchain**: `tsc` + `tsup` (ESM+CJS dual output), `vitest` for tests, `pnpm` as package manager.

---

## Packaging Scope

Phase 1 includes:
- Monorepo restructuring (Python → `packages/switchboard-python/`)
- Workspace registration (`pnpm-workspace.yaml`)
- Local build/test within repo
- Consumable package exports for future host integration

Phase 1 does **not** require:
- Public npm publish automation
- GuideRail runtime integration

---

## File Structure

```
switchboard/                              # repo root
  pnpm-workspace.yaml                    # TS workspace config
  docs/                                   # shared design docs (stays at root)
  CLAUDE.md                               # updated with new paths
  README.md                               # repo-level overview
  LICENSE
  .github/                                # CI (updated workflow paths)
  packages/
    switchboard-python/                   # ← moved from root
      src/switchboard/                    # unchanged internals
      tests/
      examples/
      pyproject.toml                      # paths stay relative (unchanged)
      .python-version
      .pre-commit-config.yaml
      README.md                           # Python-specific readme
    switchboard-typescript/               # ← new
      package.json
      tsconfig.json
      tsup.config.ts
      vitest.config.ts
      src/
        index.ts                          # Public API exports
        domain/
          models.ts                       # SemVer, ApiRange, enums, definitions, contributions, snapshots
          errors.ts                       # SwitchboardError hierarchy (8 classes)
          lifecycle.ts                    # PluginLifecycle state machine (hand-rolled)
          ports.ts                        # HookRouterPort, LoaderPort interfaces
          patch-panel.ts                  # PatchPanel aggregate root
        application/
          manifest.ts                     # parseManifest (JSON/object only)
        adapters/
          memory-hook-router.ts           # MemoryHookRouter
          registry-loader.ts              # RegistryLoader
      tests/
        domain/
          models.test.ts
          errors.test.ts
          lifecycle.test.ts
          patch-panel.test.ts
        application/
          manifest.test.ts
        adapters/
          memory-hook-router.test.ts
          registry-loader.test.ts
        integration/
          golden-path.test.ts
          activation-plan.test.ts
          introspection.test.ts
          exports.test.ts
```

---

## Implementation Steps

### Step 0: Monorepo Restructuring (Python)

Move existing Python package into `packages/switchboard-python/`. This is a file-move-only operation — no code changes.

**What moves into `packages/switchboard-python/`:**
- `src/` (package source)
- `tests/`
- `examples/`
- `pyproject.toml` (paths stay relative — `packages = ["src/switchboard"]` is unchanged)
- `.python-version`
- `.pre-commit-config.yaml`
- Python-specific dotfiles (`.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`)
- `README.md` (current root README becomes the Python-specific one)

**What stays at root:**
- `docs/` (shared across implementations)
- `.github/` (CI workflows — update paths to `packages/switchboard-python/`)
- `LICENSE`
- `CLAUDE.md` (update all commands to reference `packages/switchboard-python/`)
- New root `README.md` (brief repo-level overview pointing to both packages)

**What's created at root:**
- `pnpm-workspace.yaml` (registers `packages/*`)

**Complete when**: `cd packages/switchboard-python && pip install -e ".[dev]" && pytest` passes — identical behavior to before the move.

> **CHECKPOINT 1 — Pause for audit.** Verify Python is fully intact before any TS work begins. This is the highest-risk moment for the existing codebase.

### Step 1: TypeScript Project Scaffolding
Create `packages/switchboard-typescript/` with `package.json` (`@switchboard/core` v0.2.0), `tsconfig.json` (strict, ES2022), `tsup.config.ts`, `vitest.config.ts`.

**Complete when**: `pnpm install` succeeds, `pnpm tsc --noEmit` succeeds on empty project.

### Step 2: Domain Errors (`src/domain/errors.ts`)
Port 8 error classes extending a `SwitchboardError` base. Each stores contextual fields (e.g., `PluginNotFoundError.pluginId`, `CompatibilityError.required`/`.current`).

**Python source**: `packages/switchboard-python/src/switchboard/domain/errors.py`
**Complete when**: all Python error types exist, preserve semantic trigger conditions, expose structured fields, and are `instanceof SwitchboardError`.

### Step 3: Domain Models (`src/domain/models.ts`)
Port all value objects and entity types:
- **SemVer**: Immutable class, `static parse()`, comparison methods, `Object.freeze()` in constructor
- **ApiRange**: Immutable class, `static parse()`, `contains(version)`
- **Enums**: `as const` objects + type unions (`SlotPolicy`, `HookKind`, `HookPolicy`)
- **Definitions**: `SlotDefinition`, `HookDefinition` (with `effectivePolicy` getter)
- **Contributions**: `Contribution` base, `SlotContribution`, `HookContribution` — constructor-params-object pattern
- **Manifest types**: `ManifestContributions`, `PluginManifest`
- **Snapshot types**: `RuntimeInfo`, `RuntimeSnapshot`, `PluginSnapshot`, `SlotSnapshot`, `HookSnapshot`, `ContributionSnapshot`, `ActivationPlan` — readonly interfaces

**Python source**: `packages/switchboard-python/src/switchboard/domain/models.py`
**Complete when**: SemVer/ApiRange parsing parity tests pass, all snapshot types are readonly and exported, `effectivePolicy` derivation matches Python.

### Step 4: Domain Lifecycle (`src/domain/lifecycle.ts`)
Hand-roll the state machine (~50-70 lines). Transition map + `PluginLifecycle` class with methods: `beginActivation`, `completeActivation`, `beginDeactivation`, `completeDeactivation`, `fail`, `rollback`, `reset`. Properties: `state`, `instance`, `isActive`, `isFailed`, `lastError`.

**Python source**: `packages/switchboard-python/src/switchboard/domain/lifecycle.py`
**Complete when**: all legal and illegal transition parity tests pass.

### Step 5: Domain Ports (`src/domain/ports.ts`)
TypeScript interfaces for `HookRouterPort` and `LoaderPort`.

**Python source**: `packages/switchboard-python/src/switchboard/domain/ports.py`
**Complete when**: interfaces defined, no tests needed.

### Step 6: Adapters
- **MemoryHookRouter** (`src/adapters/memory-hook-router.ts`): Map-based handler storage, priority sorting, BROADCAST/FIRST_RESULT dispatch with failure isolation. ~100 lines.
- **RegistryLoader** (`src/adapters/registry-loader.ts`): Explicit registration of entrypoints and callables by string key. ~40 lines.

**Python sources**: `packages/switchboard-python/src/switchboard/adapters/hook_router_memory.py`, `packages/switchboard-python/src/switchboard/adapters/loader.py`
**Complete when**: priority ordering matches Python, BROADCAST collects all results (isolating failures), FIRST_RESULT stops on first non-null.

> **CHECKPOINT 2 — Pause for audit.** All building blocks exist (errors, models, lifecycle, ports, adapters) but PatchPanel hasn't been written yet. Audit the type system, naming conventions, and adapter behavior before they get wired into the aggregate root. Catching a modeling mistake here avoids rework in Steps 7–10.

### Step 7: PatchPanel (`src/domain/patch-panel.ts`)

The aggregate root (~400 lines). Split into sub-phases:

#### Step 7a: Registration and manifest indexing
- `registerManifest`, `unregister`
- Internal indexes (plugins, slots, hooks, contributions)
- Manifest validation integration (compat check, slot/hook existence)

**Complete when**: register/unregister tests pass, duplicate and validation errors match Python.

#### Step 7b: Dependency planning
- `activationPlan` (Kahn's algorithm)
- Cycle detection
- Missing/failed dependency errors
- Hard vs soft dependency semantics

**Complete when**: dependency ordering, cycle detection, and missing-dep tests pass.

#### Step 7c: Lifecycle execution
- `activate`, `deactivate`, `activateAll`
- Rollback/failure semantics
- Re-entrancy protection (boolean guard on mutating methods)

**Complete when**: activation, deactivation, rollback, failure isolation, and re-entrancy rejection tests pass.

#### Step 7d: Runtime operations and introspection
- `resolveSlot`, `emit`
- `runtimeInfo`, `snapshot`, `dumpState`
- `getPluginState`, `listPlugins`

**Complete when**: golden-path, introspection, and slot/hook dispatch tests pass.

**Python source**: `packages/switchboard-python/src/switchboard/domain/patch_panel.py`

### Step 8: Manifest Parsing (`src/application/manifest.ts`)
- `parseManifest(data: Record<string, unknown>)` performs **schema validation + normalization + domain object construction**
- Invalid manifests fail with `ManifestError` (structured, not generic)
- No partial manifest objects leak into the domain layer
- Unknown fields are ignored (forward compatibility)

**Python source**: `packages/switchboard-python/src/switchboard/application/manifest.py`
**Complete when**: all Python manifest parsing tests pass, including edge cases for missing fields, invalid types, and unknown fields.

### Step 9: Public API (`src/index.ts`)
Re-export all public types, classes, functions, and `VERSION = '0.2.0'`.

**Complete when**: all expected symbols importable from package root.

### Step 10: Integration Tests
Port test suites from Python. Must include these **load-bearing parity cases**:

- Missing hard dependency → blocked
- Circular dependency → detected and reported
- Duplicate plugin ID → `DuplicateRegistrationError`
- Incompatible API range → `CompatibilityError`
- Activation failure during dependency chain → partial rollback
- Rollback after partial activation
- Unresolved slot key → `SlotNotFoundError`
- Conflicting contribution/policy scenarios (SINGLE slot, priority ties)
- Handler exceptions during BROADCAST dispatch → isolated, other handlers still run
- Handler exceptions during FIRST_RESULT dispatch → propagated
- Full golden path: register → activate → resolve → emit → deactivate → unregister

**Python test sources**:
- `packages/switchboard-python/tests/test_golden_path.py` → `tests/integration/golden-path.test.ts`
- `packages/switchboard-python/tests/test_activation_plan.py` → `tests/integration/activation-plan.test.ts`
- `packages/switchboard-python/tests/test_introspection.py` → `tests/integration/introspection.test.ts`

**Complete when**: all integration tests pass and behavioral parity with Python is confirmed.

> **CHECKPOINT 3 — Pause for audit.** Full audit of behavioral parity. Everything is wired up and testable. Review integration test results against Python equivalents.

---

## Naming Convention Translation

| Python | TypeScript |
|--------|-----------|
| `snake_case` methods | `camelCase` methods |
| `frozen dataclass` | `readonly` class + `Object.freeze()` |
| `Enum` | `as const` object + type union |
| `Protocol` | `interface` |
| `dict[str, Any]` | `Record<string, unknown>` |
| `tuple[X, ...]` | `readonly X[]` |
| `None` (explicit absence) | `null` in return values, `undefined` for omitted input |

---

## Verification

### Step 0 (Python restructure)
1. `cd packages/switchboard-python && pip install -e ".[dev]"` — install succeeds
2. `cd packages/switchboard-python && pytest` — all existing tests pass
3. `cd packages/switchboard-python && ruff check .` — lint passes
4. `cd packages/switchboard-python && mypy src` — type check passes
5. `PYTHONPATH=packages/switchboard-python python packages/switchboard-python/examples/smoke_test.py` — smoke test passes

### Steps 1–10 (TypeScript port)
1. `pnpm install` — dependencies resolve
2. `cd packages/switchboard-typescript && pnpm tsc --noEmit` — type checking passes (strict)
3. `cd packages/switchboard-typescript && pnpm vitest run` — all tests pass
4. `cd packages/switchboard-typescript && pnpm tsup` — builds ESM + CJS bundles with `.d.ts` declarations
5. Verify public API: all expected symbols importable from `@switchboard/core`
6. Cross-reference: run Python smoke test alongside TS equivalent to confirm behavioral parity
