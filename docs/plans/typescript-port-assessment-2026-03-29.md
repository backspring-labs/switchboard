# TypeScript Port Assessment (2026-03-29)

## Scope

Reviewed the current `packages/switchboard-typescript` implementation against:

- TypeScript port plan contract (`docs/plans/typescript-port.md`)
- Existing Python runtime behavior in `packages/switchboard-python`

Also validated the package with static type checking and automated tests.

## What Looks Strong

1. **Architecture parity is high**
   - Domain/application/adapters layering maps cleanly from Python.
   - `PatchPanel` retains core responsibilities: registration, activation, planning, resolution, emission, introspection.

2. **Behavioral contract appears largely preserved**
   - Deterministic ordering logic for contributions and topo-sort tie-breaking is present.
   - Hard vs optional dependency behavior in activation planning aligns with Python.
   - Hook and slot policy handling is consistent with the shared model layer.

3. **Test coverage is substantial and green**
   - 189 TS tests currently pass.
   - Tests span domain, adapters, application parsing, and integration flows.

## Main Finding (Behavioral Divergence)

### Hook handler registration can be silently skipped in TypeScript

In TS activation, hook handler registration is conditional on both router presence **and a truthy handler string**:

```ts
if (this._hookRouter && hookContrib.handler) {
  const handler = this._loader.loadCallable(hookContrib.handler);
  this._hookRouter.registerHandler(...)
}
```

In Python, if a hook router exists, `load_callable` is always attempted for each hook contribution (including empty/default handler), so invalid handler configuration fails fast during activation.

**Why this matters:**
- TS can mark a plugin ACTIVE while silently omitting a declared hook handler when `handler` is empty.
- Python would fail activation in that case.
- This is a cross-runtime semantic mismatch.

**Recommendation:**
- Remove the `hookContrib.handler` truthiness guard and always call `loadCallable` when a hook router is configured, matching Python’s fail-fast behavior.
- Alternatively, make `handler` required in manifest parse/validation and fail earlier.

## Secondary Observations

1. **Runtime platform version formatting differs**
   - TS returns Node's `process.version` (usually prefixed with `v`).
   - Python returns numeric `major.minor.patch`.
   - If snapshots are used cross-language for strict equality assertions, this may need normalization.

2. **Environment parity checks should include installed Python deps**
   - Python tests in this environment fail at collection due to missing package install path and Python 3.10 vs `datetime.UTC` usage.
   - Not a TS issue, but limits side-by-side runtime verification in this container without environment prep.

## Validation Commands Run

- `pnpm -C packages/switchboard-typescript test` ✅
- `cd packages/switchboard-typescript && pnpm tsc --noEmit` ✅
- `cd packages/switchboard-python && pytest -q` ⚠️ (environment/import/version setup issue)

## Overall Assessment

The TypeScript port is in good shape and appears near-parity with Python for the tested/runtime-critical paths. The most important follow-up is to resolve the hook-handler activation divergence so invalid hook contributions cannot silently pass in TS.
