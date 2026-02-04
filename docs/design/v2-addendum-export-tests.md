# Switchboard v2 Addendum — Export Readiness & Host Embedding Test Suite

**Doc status:** Addendum draft (pairs with `SWITCHBOARD_V2_DESIGN_SPEC_SLOT_HOOK.md`)  
**Purpose:** Define a deterministic, automated test suite that proves Switchboard can be safely installed and embedded in a host app (e.g., Continuum) with no surprises.

---

## 1. Intent

Switchboard is designed to be a reusable, host-owned plugin runtime. To make that promise real, v2 introduces an **Export Readiness** acceptance gate:

> A CI-enforced test suite that validates packaging integrity, import safety, dependency hygiene, and a minimal host embedding flow.

This addendum defines the required checks and the pass/fail criteria.

---

## 2. Scope & Non-Goals

### In scope
- Wheel/sdist build integrity
- Clean install/import in a fresh environment
- No import-time side effects
- Public API surface stability (what hosts import)
- Minimal end-to-end embed smoke test:
  - declare Slot/Hook
  - load manifest
  - validate
  - activate (dependency planning)
  - resolve slot
  - emit hook
  - snapshot / dump_state

### Out of scope
- Security sandboxing and permissioning
- Performance benchmarking
- Networked plugin registries or auto-update workflows

---

## 3. Export Readiness Gate (Definition)

A Switchboard release candidate is **export-ready** if all checks in §4 pass on CI for:
- supported Python versions (as declared in `pyproject.toml`)
- at least one clean environment per version (fresh venv / container)
- both **wheel** and **sdist** artifacts

---

## 4. Required Checks (v2)

### 4.1 Artifact Build & Install Integrity
**Goal:** Published artifacts install cleanly and are functional.

**Checks**
1. Build `wheel` + `sdist`
2. Install from **wheel** into a fresh venv
3. Install from **sdist** into a fresh venv
4. Execute minimal smoke test (see §5)

**Pass criteria**
- build succeeds
- install succeeds without manual steps
- smoke test passes

---

### 4.2 Import Has No Side Effects
**Goal:** `import switchboard` should be safe in any host process.

**Checks**
- Run `python -c "import switchboard"` inside a fresh temp working directory.
- Assert no:
  - filesystem writes in cwd
  - spawned background threads
  - automatic plugin discovery
  - implicit logging configuration changes

**Implementation guidance**
- Prefer subprocess-based test for isolation.
- Optionally monkeypatch file IO in a dedicated test to detect reads/writes during import.

**Pass criteria**
- import succeeds
- no side effects detected

---

### 4.3 Dependency Hygiene (Core vs Extras)
**Goal:** core install remains lean; optional adapters live behind extras.

**Checks**
- Verify `pyproject.toml` core dependencies are minimal.
- Ensure optional features (examples):
  - entry-point loader
  - YAML formatting
  - rich/pretty console output
  - async router adapters
  are gated behind `[project.optional-dependencies]`.

**Pass criteria**
- core `pip install switchboard` does not require optional adapter deps
- importing `switchboard` does not import optional adapter modules

---

### 4.4 Public API Surface Check
**Goal:** hosts (e.g., Continuum) can import stable symbols only.

**Checks**
- Verify top-level imports succeed:
  - `from switchboard import PatchPanel`
  - `from switchboard import ...` (any additional intended exports)
- Verify non-public/internal modules are not required for typical host use.

**Pass criteria**
- intended top-level imports succeed
- no host integration examples import internal modules

**Recommended practice**
- Maintain `switchboard.__all__` and test it via a golden snapshot if you want strictness.

---

### 4.5 No Global State / Multi-Panel Isolation
**Goal:** multiple PatchPanels in-process do not bleed state.

**Checks**
- Create two PatchPanels in the same process.
- Register distinct Slot/Hook declarations and plugin manifests.
- Activate and emit separately.
- Compare snapshots to ensure isolation.

**Pass criteria**
- each PatchPanel sees only its own state
- no shared registries, singleton routers, or leaked patches

---

### 4.6 Host Embedding Smoke Test (Canonical)
**Goal:** prove the minimal “Continuum-style embed” works.

This is the most important test. It should be small, deterministic, and run fast.

**Required flow**
1. Construct `PatchPanel`
2. Declare:
   - one Slot with a contract (simple schema)
   - one Hook with a signature and error strategy
3. Load plugin manifests from in-memory loader
4. Validate manifests
5. Activate all plugins with dependency planning
6. Resolve Slot patches and assert deterministic ordering
7. Emit Hook and assert policy behavior
8. Generate runtime snapshot and dump_state output

**Pass criteria**
- all steps succeed
- results match expected deterministic outputs

---

## 5. Canonical Smoke Test Scenario (Illustrative)

### 5.1 Host declarations
- Slot: `ui.slot.left_nav` (cardinality `many`)
  - contract: UI descriptor requires `{component_key, props}`
- Hook: `app.starting`
  - signature: `handler(payload) -> None`
  - error strategy: `LOG_AND_CONTINUE` (or default)

### 5.2 Plugins
- Plugin `core` provides:
  - one SlotPatch: `NavGroup` descriptor
  - one HookPatch: logs a startup message
- Plugin `feature` depends on `core`
  - adds another SlotPatch with order 50
  - adds another HookPatch

### 5.3 Assertions
- Activation plan is topological: `core` then `feature`
- Slot resolution ordering is stable:
  - sorted by `(order, plugin_id, patch_id)`
- Hook emission returns:
  - `EmissionResult` via `emit_full()`
  - errors collected per selected strategy
- Snapshot contains:
  - both plugins active
  - patches registered against the intended Slot/Hook
  - no unexpected targets

---

## 6. CI Integration (Recommended)

### 6.1 Suggested CI stages
1. Lint/type check (optional but recommended)
2. Unit tests
3. Build artifacts (wheel/sdist)
4. Export readiness suite (fresh env install + smoke)
5. Publish gate (manual)

### 6.2 Artifact retention
- Upload `dump_state()` output and `RuntimeSnapshot` JSON as CI artifacts for easy debugging.

---

## 7. Definition of Done (Addendum)

This addendum is complete when:
- the checks in §4 are implemented and run in CI
- the canonical host embedding smoke test exists and is stable
- failures provide actionable diagnostics (snapshot/dump included)

---

## Appendix A: Suggested Test Names

- `test_export_build_wheel_and_sdist_install_ok`
- `test_import_no_side_effects`
- `test_dependencies_core_vs_extras`
- `test_public_api_exports`
- `test_two_panels_are_isolated`
- `test_host_embedding_smoke_end_to_end`

---

## Appendix B: Optional “Strict Mode” Enhancements (Future)

- Enforce a golden snapshot of `switchboard.__all__`
- Enforce a “no file IO on import” monkeypatch
- Add a plugin manifest compatibility matrix test (api_level/capability gating)
