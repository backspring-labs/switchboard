# Switchboard Intent and Background

## Why Switchboard exists

Most projects start with a simple need: “let me add one more feature without editing the core.” Then you blink, and you’ve got:

- a pile of `if feature_enabled:` branches
- hand-rolled registries scattered across modules
- “plugin-ish” code paths with inconsistent lifecycle and error handling
- fragile import side effects (“just importing the module registers things…”)
- no consistent way to introspect what’s actually wired in production

Switchboard exists to stop that drift early.

It provides a **single, reusable, deterministic extension mechanism** that hosts can adopt once and then scale across many domains, without re-inventing registration, ordering, compatibility, and introspection each time.

The goal isn’t “plugins” as a buzzword. The goal is **controlled extensibility**: predictable, testable, versionable growth.

## The design intent in one line

Switchboard is a **host-owned extension contract system** that enables third-party (or internal) plugins to contribute behavior, descriptors, and artifacts through stable extension points — with deterministic selection and strong introspection.

## What “host-owned” really means

Switchboard assumes the **host defines the seams**.

- The host defines extension points and their contracts.
- Plugins can only *contribute* to those declared seams.
- Plugins don’t get to invent new core behaviors by “showing up.”
- The host controls invocation, ordering, lifecycle, and context.

This prevents the usual plugin-system trap where “anything can hook anything,” and the core becomes a mystery box.

## The philosophy: extension points, not “hooks”

Switchboard prefers **extension points** because the mental model is different:

- A “hook” sounds like “I can inject myself anywhere.”
- An extension point sounds like “the host intentionally exposes a seam.”

That’s the posture you want if you care about:
- long-term maintainability
- DDD boundaries
- predictable behavior in production
- the ability to ship host upgrades without breaking everything

## The core problem Switchboard solves

There are really four problems every plugin system ends up needing to solve:

1) **Discovery**: what extensions exist and where do they come from?  
2) **Compatibility**: does this extension match what the host expects?  
3) **Determinism**: if two plugins contribute, who wins and why?  
4) **Observability**: can I explain what’s active and what happened at runtime?

Most homegrown systems solve #1 and hand-wave #2–#4 until it hurts.

Switchboard makes #2–#4 first-class.

## What “deterministic” means in practice

Determinism is a feature, not a preference.

If you can’t guarantee stable ordering and selection, you get:
- non-reproducible bugs
- “works on my machine” plugin behavior
- production-only wiring issues
- plugin conflicts that are impossible to reason about

Switchboard treats determinism as a contract:
- selection is based on declared priority + stable tie-break
- multicast invocation order is stable
- introspection can explain exactly what was eligible, chosen, and invoked

## Why contracts matter (and why versioning matters even more)

Without enforceable contracts, extension points become vague social agreements.

You need a way to say:
- “this extension point expects *this shape* of input”
- “it produces *this shape* of output”
- “this contract is versioned, so we can evolve it safely”

That’s why Switchboard elevates **Contract** to a first-class concept:
- it gives you a stable compatibility surface
- it enables validation and testing
- it sets you up for long-term evolution without breaking plugins

This is also what makes the system viable for UI extension later: UI contributions are *still* just contract-governed contributions — not special snowflakes.

## Why contribution “kinds” exist

A lot of plugin systems assume plugins contribute code and only code.

But modern extensibility needs to support:
- behavior (a callable)
- configuration (a descriptor)
- assets/bundles (an artifact)

Switchboard’s intent is to treat all three as **contributions to extension points**, so the host can:
- validate them
- version them
- introspect them
- order them
- activate/deactivate them under lifecycle control

The key is that Switchboard does not define what a descriptor *means*.
It only defines how a host can safely accept one.

## DDD + Hex alignment (why Switchboard won’t sabotage your architecture)

Switchboard is meant to be imported into projects that care about boundaries.

That’s why the invocation model passes a narrow `context` containing ports/services rather than giving plugins access to host internals.

The intent is:
- plugins can depend on **ports**
- the host provides adapters behind those ports
- plugins don’t reach across bounded contexts by accident
- you can unit test plugins with fake contexts easily

In other words: extensibility without turning your domain model into a junk drawer.

## Lifecycle intent: simple but real

The lifecycle exists for one reason: to prevent “half-loaded plugins” and “invocation during teardown.”

Even a simplified lifecycle gives you:
- a place to validate and wire dependencies (`STARTING`)
- a clear gate for when invocation is allowed (`ACTIVE`)
- a controlled shutdown phase (`STOPPING`)
- a failure state that can be detected and reported (`FAILED`)

You’re not trying to recreate OSGi’s complexity.
You’re trying to avoid the chaos that happens when lifecycle is implicit.

## What Switchboard is *not*

It’s important that Switchboard stays small and boring:

- Not a UI framework
- Not an orchestration engine
- Not an application shell
- Not a dependency injection container
- Not a policy engine
- Not a sandbox / security boundary (yet)

Switchboard is a **composition primitive**: a way to plug things in intentionally.

## The long-term intent (without baking it into v1)

Even though v1 stays narrow, the architecture should be compatible with future needs like:

- richer compatibility resolution (semver ranges, host capability constraints)
- async/cancellation/timeouts
- stronger error envelopes and invocation reports
- packaging discovery via standard mechanisms
- UI extension for web/mobile via artifact contributions

The key is: those can be added by extending the contract and contribution model — not by rewriting the foundation.

## Success criteria

Switchboard is “working” when:

- A host can declare extension points as stable contracts.
- Plugins can be added/removed without changing host core.
- Conflicts are resolved deterministically and explainably.
- Failures are observable and attributable to a plugin/contribution.
- The system remains small enough to be imported into many projects without dragging in a worldview.

## Why this matters for your ecosystem

You’re building multiple systems that will evolve at different speeds. Switchboard is how you avoid:

- each project inventing its own plugin conventions
- inconsistent lifecycles across hosts
- UI extensibility becoming a special-case snowball
- “integration projects” turning into glue-code sprawl

Switchboard becomes the consistent seam-definition mechanism across your universe — not by naming those systems, but by enabling the same extensibility pattern everywhere.
