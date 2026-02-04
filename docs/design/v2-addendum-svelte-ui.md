# Switchboard v2 Addendum — Svelte UI Slot Contributions (Continuum Bridge)

**Doc status:** Addendum draft (pairs with `SWITCHBOARD_V2_DESIGN_SPEC_SLOT_HOOK.md`)  
**Scope:** UI Slot contributions designed for a Svelte-based Continuum control plane  
**Principle:** Keep Switchboard UI-framework agnostic; put Svelte/runtime specifics in Continuum adapters.

---

## 1. Intent

Enable plugins to contribute UI into **Continuum** via Switchboard **Slots** in a way that is:

- **host-owned** (Continuum declares what can be contributed)
- **deterministic** (stable ordering and resolution)
- **safe by default** (validation before activation)
- **observable** (introspection and explainability)
- **portable** (plugins contribute *descriptors* first; component bundling is an advanced option)

This addendum spec’s a minimal, durable bridge that does not force Switchboard to understand Svelte.

---

## 2. Architecture Boundary

### Switchboard responsibilities (generic)
Switchboard provides the **contracted Slot runtime**:
- slot declarations + contracts (shape requirements)
- manifest validation (patch payload checks)
- deterministic patch ordering and selection
- introspection (`snapshot`, `explain_slot`, `dump_state`)

### Continuum responsibilities (Svelte-specific)
Continuum provides the **UI adapter layer**:
- maps slot patch payloads → Svelte components
- owns component registry, rendering strategy, navigation/actions wiring
- owns bundling/lazy loading and security posture for client-side code
- owns UX conventions (icon sets, nav semantics, layout regions)

**Rule:** Switchboard never executes Svelte code and does not interpret UI beyond validating a declared contract.

---

## 3. Recommended Pattern: Descriptor-Based UI Patches (Default)

Plugins contribute **UI descriptors** (data), not compiled Svelte components.

### 3.1 Why this is the default
- avoids hard coupling Switchboard to Svelte/Vite
- keeps plugin contributions reviewable and testable
- avoids remote-code-loading risks in the browser
- makes validation and introspection straightforward

---

## 4. Slot Taxonomy (Continuum Host Declares)

Continuum should declare a canonical set of UI slots. Example:

- `ui.slot.header.left`
- `ui.slot.header.right`
- `ui.slot.left_nav`
- `ui.slot.main.toolbar`
- `ui.slot.main.content` (often “page contributions”)
- `ui.slot.footer`
- `ui.slot.settings.sections`

Each slot also declares:
- cardinality: `one | many`
- ordering rules
- contract schema (see §5)

---

## 5. Slot Contracts for UI Patches (Switchboard-Level Feature)

V2 should support **SlotContract** validation. Continuum supplies the contract, Switchboard enforces it.

### 5.1 Minimal UI SlotContract schema
A Slot contract for UI descriptor patches should validate these fields:

**UIComponentDescriptor**
- `component_key: str`  
  A key into Continuum’s Svelte component registry (e.g. `"NavGroup"`, `"HeaderWidget"`, `"QuickAction"`).
- `props: dict`  
  JSON-serializable props passed to the Svelte component.
- `actions: list[UIAction]` *(optional)*  
  For navigation/click behaviors without executing arbitrary code.
- `order: int` *(optional)*  
  For deterministic ordering (lower first).
- `group: str` *(optional)*  
  Enables grouping in navigation or toolbars.

**UIAction**
- `kind: "route" | "event" | "external_link"`
- `target: str` (route id, event id, or URL)
- `label: str` *(optional)*

### 5.2 Switchboard validation rules (recommended)
- Ensure patch payload conforms to SlotContract
- Enforce determinism:
  - stable ordering key: `(order, plugin_id, patch_id)` with defaults
- Enforce redaction policy in dump tools (no secrets in props by default)

---

## 6. Patch Metadata Conventions for UI

Reuse v2 reserved metadata keys (already in v2 spec), with UI-friendly guidance:

- `metadata.ui.title: str` (display name)
- `metadata.ui.icon: str` (icon key; Continuum owns icon set)
- `metadata.roles: list[str]` (role gating)
- `metadata.feature_flags: dict[str, bool]` (feature gating)
- `metadata.tags: list[str]` (classification)

**Rule:** Switchboard may support filtering helpers (e.g., role filter), but Continuum decides policy.

---

## 7. Continuum Rendering Adapter (Svelte)

Continuum implements a **SlotRenderer** that:
1. asks Switchboard for resolved patches:
   - `panel.resolve_slot("ui.slot.left_nav", context=...) -> list[SlotPatch]`
2. converts each patch payload into a Svelte component instance:
   - `component = registry.get(descriptor.component_key)`
3. renders components into the target region (slot)

### 7.1 Component registry (Continuum)
Continuum maintains `component_key -> Svelte component` mapping:
- static registry for core components
- optional plugin-owned component packages (advanced; §10)

---

## 8. Example: Descriptor Patch Manifest

```yaml
id: "com.example.pluginA"
name: "Plugin A"
version: "0.3.0"

plugin_requires_host_api_level: 1
capabilities_required:
  - "switchboard.manifest_validation"
  - "switchboard.introspection"

patches:
  - kind: "slot"
    slot_id: "ui.slot.left_nav"
    handler: "plugin_a.ui:nav_patch"   # returns descriptor(s)
    metadata:
      id: "pluginA.leftnav"
      tags: ["ui", "nav"]
      roles: ["admin"]
      ui:
        title: "Plugin A"
        icon: "spark"
```

Where `plugin_a.ui:nav_patch()` returns:

```json
{
  "component_key": "NavGroup",
  "props": {
    "title": "Plugin A",
    "items": [
      {"label": "Overview", "action": {"kind": "route", "target": "pluginA.overview"}},
      {"label": "Jobs", "action": {"kind": "route", "target": "pluginA.jobs"}}
    ]
  },
  "order": 50,
  "group": "plugins"
}
```

---

## 9. Introspection UX (Continuum “Wiring View”)

Continuum should expose a diagnostics view backed by Switchboard:

- “Slot wiring”: for a slot, show all resolved patches and their ordering keys
- “Why not shown”: show role/feature gating decisions
- “Activation plan”: show dependency order and blocked states
- “Hook activity”: show recent emissions and handler outcomes (if enabled)

This is a high leverage feature for real-world operation.

---

## 10. Advanced Option: Plugin-Provided Svelte Components (Deferred)

If you later want plugins to ship actual Svelte components:

### 10.1 What changes (Continuum)
Continuum must own:
- bundling strategy (Vite/Rollup)
- distribution and trust model (signed bundles? trusted-only?)
- version compatibility (Svelte runtime version; component API)
- lazy loading and caching

### 10.2 What changes (Switchboard)
Ideally nothing beyond:
- allowing UI descriptors to reference `component_key` that can be resolved to a dynamic module
- optional contract fields:
  - `module_ref` (where to import from)
  - `export_name`

**Recommendation:** treat this as `0.3+` / `1.0` scope unless you have a strong need now.

---

## 11. Versioning and Compatibility (UI Bridge)

### 11.1 Continuum UI API level
Continuum should maintain a `continuum_ui_api_level` (integer) that expresses
compatibility of its UI descriptor schema and component registry expectations.

Plugins may declare:
- `requires_continuum_ui_api_level: int`

Continuum can enforce this during manifest validation (host-owned).

### 11.2 Capability flags
Continuum provides capability flags in `capabilities_provided`, such as:
- `continuum.ui.descriptor_patches`
- `continuum.ui.component_registry_v1`
- `continuum.ui.actions_v1`

Plugins can require them to ensure feature detection is explicit.

---

## 12. Acceptance Criteria (Addendum)

This addendum is “done” when:

1. Continuum can declare UI slots with SlotContracts.
2. A plugin can contribute descriptor patches into those slots.
3. Switchboard validates manifests before activation (slot exists, contract passes).
4. Slot resolution yields deterministic ordering across runs.
5. Continuum renders resolved descriptor patches into Svelte UI.
6. Switchboard introspection can explain what contributed to a slot and why.
7. A “wiring view” in Continuum can be built using `snapshot/explain`.

---

## 13. Implementation Notes (Suggested Sequencing)

1. **Switchboard**: SlotContract + manifest validation + deterministic ordering + explain_slot.
2. **Continuum**: slot declarations + component registry + SlotRenderer (descriptor pattern).
3. **Examples**: sample plugin that contributes to `ui.slot.left_nav` and `ui.slot.header.right`.
4. **Diagnostics**: Continuum wiring view using Switchboard snapshot.

---

## Appendix A: Minimal SlotContract structure (illustrative)

```python
@dataclass(frozen=True)
class SlotContract:
    kind: Literal["ui_descriptor"]
    schema_version: int = 1
    required_fields: tuple[str, ...] = ("component_key", "props")
    allow_actions: bool = True
    props_json_serializable: bool = True
```

---

## Appendix B: Suggested reserved Slot IDs (starter set)

- `ui.slot.header.left`
- `ui.slot.header.right`
- `ui.slot.left_nav`
- `ui.slot.main.toolbar`
- `ui.slot.footer`
- `ui.slot.settings.sections`
