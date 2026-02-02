# Switchboard Terminology Alignment — UI Slots, Hooks, and PatchPanel

**Date:** 2026-02-01  
**Status:** Agreed vocabulary + rationale (ready to use in spec/docs)

---

## Context

We’ve been iterating on a DDD + Hexagonal Architecture framing for **Switchboard** (the branded project),
and we wanted naming that:

- feels **modern** (less “ExtensionPoint” / Eclipse-OSGi terminology),
- matches a **switchboard** mental model,
- cleanly supports **Continuum-style UI extensibility** (primarily capability slots),
- still supports **event listeners / command overrides** in a way that doesn’t pollute the UI model,
- keeps imports and API ergonomics idiomatic in Python.

During the discussion we established a helpful split:

- UI extension is mostly about **fixed but responsive layout anchors**
- events/overrides are about **interception and ordered handlers**
- the registry that holds all of this should feel like “the board where routing happens”

---

## The Alignment (Final Terms)

### Project / Package vs Core Engine Object
- **Switchboard** = branded project name + top-level Python package (`switchboard`)
- **PatchPanel** = the core registry/resolution engine exposed via:
  - `from switchboard import PatchPanel`

This keeps the brand at the package level and the technical noun at the core object level.

---

## Core Concepts

### 1) Slot (UI Anchor Position)
A **Slot** is a *host-defined UI anchor* in a fixed-but-responsive layout (not draggable/dockable).
It represents a named area where UI contributions can be rendered.

**Why “Slot”:**
- Neutral and extensible (UI *and* non-UI attachment points)
- Familiar across ecosystems without tying to a specific UI framework
- Fits the Switchboard/PatchPanel mental model: a named place to plug in a contribution

**Examples (IDs):**
- `ui.slot.header`
- `ui.slot.left_nav`
- `ui.slot.main`
- `ui.slot.right_rail`
- `ui.slot.footer`
- `ui.slot.modal`
- `ui.slot.toast_stack`

**Important property:** Slot cardinality  
Each Slot should declare whether it supports:
- `ONE` — single occupant (e.g., `ui.slot.main`)
- `MANY` — ordered list/stack (e.g., `ui.slot.left_nav`, toolbar buttons)

---

### 2) Hook (Events, Interception, Command Overrides)
A **Hook** is a *host-defined interception point* for:
- lifecycle events (e.g., startup),
- event listeners,
- “before/after/around” pipelines,
- command overrides / interception.

**Why “Hook”:**
- Modern and familiar across ecosystems
- Communicates interception and ordered handlers clearly
- Keeps event semantics separate from UI layout semantics

**Examples (IDs):**
- `app.starting`
- `app.stopping`
- `command.file.open.before`
- `command.file.open.around`
- `command.file.open.after`

**Command overrides**
Command overrides should be expressed as **hook behavior** (ordered interceptors),
rather than inventing a separate override mechanism.

---

### 3) PatchPanel (Registry + Resolver)
The **PatchPanel** is the central registry and resolver for Slots and Hooks.

It holds:
- declared **Slots** (targets)
- declared **Hooks** (targets)
- plugin-provided **Patches** (contributions)
- resolution rules (ordering, priority, cardinality)

**Why “PatchPanel” works with “Switchboard”:**
- Same underlying metaphor: a central board where connections are made
- “Patch panel” is widely understood by engineers (telecom/audio/networking)
- It feels technical and modern without being overly cute

---

## Contributions

### Patch (Plugin Contribution)
A **Patch** is the generic word for what plugins contribute to the PatchPanel.

Recommended typed variants (optional but clarifying):
- `SlotPatch` — UI contributions that render into a Slot
- `HookPatch` — event handlers / interceptors registered on a Hook
- `CommandPatch` — register a new command (optional)
- `CommandOverridePatch` — prefer expressing as `HookPatch` on a command hook

**Why “Patch”:**
- Works naturally with PatchPanel
- Avoids the need to introduce “Plug/Jack” terminology unless desired
- Unifies UI + events under a single contribution concept

---

## Mapping to the Earlier “ExtensionPoint” Vocabulary

| Prior Term (OSGi-ish) | New Term (Aligned) | Meaning |
|---|---|---|
| ExtensionPoint | Slot / Hook | Host-defined target (UI anchor vs event pipeline) |
| Contribution | Patch | Plugin-provided implementation/handler |
| ExtensionPointCatalog | PatchPanel | Registry + resolver + invocation |

---

## DDD + Hex Fit (Why this is appropriate)

Even though Switchboard is “infrastructure,” it has real invariants worth protecting:

- deterministic loading and resolution
- lifecycle gating (what can run when)
- compatibility checks (contracts/versions)
- stable ordering and conflict resolution
- failure isolation and diagnosis

That makes DDD + Hex useful here, *as long as the domain stays small*.

**Bounded Context:** Plugin Runtime / Extension Management  
**Key “domain nouns”:** PatchPanel, Slot, Hook, Patch, PluginManifest, LifecycleState

Hex framing remains clean:
- Domain owns rules (what is a valid Slot/Hook/Patch and how resolution works)
- Application orchestrates (load, activate, deactivate, invoke)
- Adapters implement discovery/loading/storage/logging

---

## Suggested API Shape (Illustrative)

### PatchPanel responsibilities
- declare targets:
  - `declare_slot(slot_id, contract, cardinality, …)`
  - `declare_hook(hook_id, signature, ordering, …)`
- register patches:
  - `register_patch(target_id, patch)`
  - or typed helpers: `register_region_patch`, `register_hook_patch`
- resolve/invoke:
  - `resolve_slot(slot_id) -> Patch | [Patch]`
  - `emit_hook(hook_id, event) -> results`

### Switchboard (facade) responsibilities (optional, later)
- discovery + loading + lifecycle
- populates a PatchPanel
- exposes a stable surface for hosts (Continuum, SquadOps, etc.) **without** coupling the domain

---

## Design Logic Summary (Why these names)

1. **Slot** matches the core extensibility need: a named attachment point (UI anchors *and* non-UI endpoints).
2. **Hook** is reserved for interception semantics (events/overrides), preventing conceptual mush.  
3. **PatchPanel** cleanly represents the central “board” where everything is registered/resolved.  
4. **Switchboard** stays as the branded project/package; **PatchPanel** is the crisp technical engine.  
5. The set works in docs *and* in code, and fits DDD/Hex boundaries without over-modeling.

---

## Next Steps (Optional)
- Update the Switchboard intent/spec terminology section with:
  - Slot / Hook / PatchPanel / Patch
- Define the minimal v1 resolution rules:
  - Slot cardinality (`ONE|MANY`)
  - Patch ordering (priority + stable tie-breakers)
  - Hook pipeline semantics (`before|after|around` or just ordered handlers)
- Add diagnostics primitives:
  - “why this patch won” explanations (priority, compatibility, lifecycle state)

---
