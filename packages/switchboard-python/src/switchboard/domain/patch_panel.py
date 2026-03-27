"""Switchboard PatchPanel - the central registry and resolver."""

from __future__ import annotations

import importlib.metadata
import json
import sys
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from switchboard.domain.errors import (
    CompatibilityError,
    DuplicateRegistrationError,
    HookNotFoundError,
    LifecycleError,
    PluginNotFoundError,
    SlotNotFoundError,
)
from switchboard.domain.lifecycle import PluginLifecycle, PluginState
from switchboard.domain.models import (
    ActivationPlan,
    Contribution,
    ContributionSnapshot,
    HookContribution,
    HookDefinition,
    HookSnapshot,
    PluginManifest,
    PluginSnapshot,
    RuntimeInfo,
    RuntimeSnapshot,
    SemVer,
    SlotContribution,
    SlotDefinition,
    SlotPolicy,
    SlotSnapshot,
)

if TYPE_CHECKING:
    from switchboard.domain.ports import HookRouterPort, LoaderPort

# Current Switchboard version for compatibility checks
SWITCHBOARD_VERSION = SemVer.parse("0.2.0")


class PatchPanel:
    """Central registry and resolver for plugins, slots, and hooks.

    The PatchPanel is the aggregate root of the Switchboard domain. It manages:
    - Plugin registration and lifecycle
    - Slot and hook definitions
    - Contribution resolution with priority ordering
    - Hook emission delegation to the router

    Thread Safety:
        All public methods are thread-safe. Mutations acquire an exclusive lock,
        while reads acquire a shared lock (implemented via RLock for simplicity in V1).
    """

    def __init__(
        self,
        slots: list[SlotDefinition],
        hooks: list[HookDefinition],
        hook_router: HookRouterPort | None = None,
        loader: LoaderPort | None = None,
    ) -> None:
        """Initialize a PatchPanel with slot and hook definitions.

        Args:
            slots: List of slot definitions the host exposes.
            hooks: List of hook definitions the host exposes.
            hook_router: Adapter for hook dispatch. If None, emit() will raise.
            loader: Adapter for loading plugin entrypoints. If None, activate() will raise.
        """
        self._lock = threading.RLock()

        # Slot registry: key -> definition
        self._slots: dict[str, SlotDefinition] = {}
        for slot in slots:
            if slot.slot_key in self._slots:
                raise ValueError(f"Duplicate slot key: {slot.slot_key}")
            self._slots[slot.slot_key] = slot

        # Hook registry: key -> definition
        self._hooks: dict[str, HookDefinition] = {}
        for hook in hooks:
            if hook.hook_key in self._hooks:
                raise ValueError(f"Duplicate hook key: {hook.hook_key}")
            self._hooks[hook.hook_key] = hook

        # Plugin registry: plugin_id -> (manifest, lifecycle)
        self._plugins: dict[str, tuple[PluginManifest, PluginLifecycle]] = {}

        # Contribution registries
        self._slot_contributions: dict[str, list[SlotContribution]] = {
            key: [] for key in self._slots
        }
        self._hook_contributions: dict[str, list[HookContribution]] = {
            key: [] for key in self._hooks
        }

        # Adapters
        self._hook_router = hook_router
        self._loader = loader

        # Flag to detect re-entrant registration from within hooks
        self._in_hook_emission = threading.local()

    # =========================================================================
    # Plugin Registration
    # =========================================================================

    def register_manifest(self, manifest: PluginManifest) -> None:
        """Register a plugin from its manifest.

        This validates the manifest and moves the plugin to READY state.
        The plugin's entrypoint is NOT loaded at this stage.

        Args:
            manifest: The plugin manifest.

        Raises:
            DuplicateRegistrationError: If the plugin is already registered.
            CompatibilityError: If the plugin is incompatible with this Switchboard version.
            SlotNotFoundError: If a contribution targets an unknown slot.
            HookNotFoundError: If a contribution targets an unknown hook.
        """
        self._check_not_in_hook()

        with self._lock:
            if manifest.plugin_id in self._plugins:
                raise DuplicateRegistrationError(manifest.plugin_id)

            # Check Switchboard version compatibility
            if not manifest.requires_switchboard.contains(SWITCHBOARD_VERSION):
                raise CompatibilityError(
                    manifest.plugin_id,
                    str(manifest.requires_switchboard),
                    str(SWITCHBOARD_VERSION),
                )

            # Validate contribution targets exist
            for slot_contrib in manifest.contributions.slots:
                if slot_contrib.slot_key not in self._slots:
                    raise SlotNotFoundError(slot_contrib.slot_key)

            for hook_contrib in manifest.contributions.hooks:
                if hook_contrib.hook_key not in self._hooks:
                    raise HookNotFoundError(hook_contrib.hook_key)

            # Create lifecycle and register
            lifecycle = PluginLifecycle(manifest.plugin_id)
            self._plugins[manifest.plugin_id] = (manifest, lifecycle)

    def unregister(self, plugin_id: str) -> None:
        """Unregister a plugin.

        The plugin must be in READY or FAILED state (not ACTIVE).

        Args:
            plugin_id: The plugin to unregister.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
            LifecycleError: If the plugin is currently active.
        """
        self._check_not_in_hook()

        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)

            _manifest, lifecycle = self._plugins[plugin_id]

            if lifecycle.state == PluginState.ACTIVE:
                raise LifecycleError(plugin_id, "unregister", lifecycle.state.value)

            # Remove contributions from slot registries
            for slot_key, contributions in self._slot_contributions.items():
                self._slot_contributions[slot_key] = [
                    c for c in contributions if c.plugin_id != plugin_id
                ]

            del self._plugins[plugin_id]

    # =========================================================================
    # Plugin Lifecycle
    # =========================================================================

    def activate(self, plugin_id: str) -> None:
        """Activate a registered plugin.

        This loads the plugin entrypoint, instantiates it, calls activate(),
        and registers all contributions.

        Args:
            plugin_id: The plugin to activate.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
            LifecycleError: If the plugin is not in READY state.
            RuntimeError: If no loader is configured.
        """
        self._check_not_in_hook()

        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)

            self._activate_internal(plugin_id)

    def _unregister_contributions(self, plugin_id: str, manifest: PluginManifest) -> None:
        """Unregister all contributions for a plugin.

        This is used during deactivation and rollback to clean up
        slot contributions and hook handlers.

        Args:
            plugin_id: The plugin whose contributions to remove.
            manifest: The plugin's manifest (for contribution list).
        """
        # Unregister hook handlers from router and local tracking
        for hook_contrib in manifest.contributions.hooks:
            if self._hook_router is not None:
                self._hook_router.unregister_handler(
                    hook_contrib.hook_key, hook_contrib.contribution_id
                )
        # Remove from local hook contribution tracking
        for hook_key in self._hook_contributions:
            self._hook_contributions[hook_key] = [
                c for c in self._hook_contributions[hook_key] if c.plugin_id != plugin_id
            ]

        # Remove slot contributions
        for slot_key in self._slot_contributions:
            self._slot_contributions[slot_key] = [
                c for c in self._slot_contributions[slot_key] if c.plugin_id != plugin_id
            ]

    def deactivate(self, plugin_id: str) -> None:
        """Deactivate an active plugin.

        This unregisters contributions, calls deactivate() on the instance,
        and returns the plugin to READY state.

        Args:
            plugin_id: The plugin to deactivate.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
            LifecycleError: If the plugin is not in ACTIVE state.
        """
        self._check_not_in_hook()

        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)

            manifest, lifecycle = self._plugins[plugin_id]

            # Begin deactivation (ACTIVE -> STOPPING)
            lifecycle.begin_deactivation()

            try:
                # Unregister contributions
                self._unregister_contributions(plugin_id, manifest)

                # Call deactivate() if the plugin has it
                if lifecycle.instance is not None and hasattr(lifecycle.instance, "deactivate"):
                    lifecycle.instance.deactivate({})

                # Complete deactivation (STOPPING -> READY)
                lifecycle.complete_deactivation()

            except Exception as e:
                # Mark as failed if deactivation fails
                lifecycle.fail(e)
                raise

    def activation_plan(self) -> ActivationPlan:
        """Compute the activation order for all registered plugins.

        Builds a dependency graph from `requires` declarations and performs
        a topological sort. Detects cycles and missing dependencies.

        Returns:
            ActivationPlan with:
            - order: Plugin IDs in activation order (ready plugins only)
            - blocked: Dict of plugin_id -> reason for plugins that can't activate
            - cycles: List of detected dependency cycles
        """
        with self._lock:
            return self._compute_activation_plan()

    def _compute_activation_plan(self) -> ActivationPlan:
        """Internal: compute activation plan (caller must hold lock)."""
        # Build dependency graph
        # graph[plugin] = set of plugins that must be activated first
        graph: dict[str, set[str]] = {}
        blocked: dict[str, str] = {}

        # Collect all registered plugin IDs
        registered = set(self._plugins.keys())

        for plugin_id, (manifest, lifecycle) in self._plugins.items():
            # Skip already active or failed plugins
            if lifecycle.state == PluginState.ACTIVE:
                continue
            if lifecycle.state == PluginState.FAILED:
                blocked[plugin_id] = "plugin in failed state"
                continue

            # Check hard dependencies
            missing_deps = []
            for dep in manifest.requires:
                if dep not in registered:
                    missing_deps.append(dep)

            if missing_deps:
                blocked[plugin_id] = f"missing dependencies: {', '.join(missing_deps)}"
                continue

            # Build dependency set (hard deps only for blocking)
            deps: set[str] = set()
            for dep in manifest.requires:
                dep_lifecycle = self._plugins[dep][1]
                if dep_lifecycle.state == PluginState.FAILED:
                    blocked[plugin_id] = f"dependency '{dep}' is in failed state"
                    break
                if dep in blocked:
                    blocked[plugin_id] = f"dependency '{dep}' is blocked"
                    break
                deps.add(dep)
            else:
                # Add optional deps that exist and are activatable (for ordering only)
                for opt_dep in manifest.optional_requires:
                    if opt_dep in registered and opt_dep not in blocked:
                        opt_lifecycle = self._plugins[opt_dep][1]
                        if opt_lifecycle.state != PluginState.FAILED:
                            deps.add(opt_dep)

                graph[plugin_id] = deps

        # Detect cycles using Kahn's algorithm
        # (also produces topological order)
        # in_degree[p] = number of unprocessed dependencies p has
        in_degree: dict[str, int] = {}
        for plugin_id, deps in graph.items():
            # Only count dependencies that are in the graph (activatable)
            activatable_deps = [d for d in deps if d in graph]
            in_degree[plugin_id] = len(activatable_deps)

        # Start with nodes that have no unprocessed dependencies
        queue = sorted([p for p, d in in_degree.items() if d == 0])
        order: list[str] = []

        while queue:
            # Take the first (lexicographically for determinism)
            plugin = queue.pop(0)
            order.append(plugin)

            # Reduce in_degree for plugins that depend on this one
            for dependent, deps in graph.items():
                if plugin in deps and dependent not in order:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0 and dependent not in queue:
                        # Insert in sorted position for deterministic order
                        queue.append(dependent)
                        queue.sort()

        # Any remaining nodes with in_degree > 0 are in cycles
        cycles: list[tuple[str, ...]] = []
        remaining = [p for p in graph if p not in order]
        if remaining:
            # Find the cycle(s)
            cycles = self._find_cycles(graph, remaining)
            for plugin_id in remaining:
                blocked[plugin_id] = "involved in dependency cycle"

        return ActivationPlan(
            order=tuple(order),
            blocked=blocked,
            cycles=tuple(cycles),
        )

    def _find_cycles(
        self, graph: dict[str, set[str]], candidates: list[str]
    ) -> list[tuple[str, ...]]:
        """Find cycles in the dependency graph among candidates."""
        cycles: list[tuple[str, ...]] = []
        visited: set[str] = set()

        def dfs(node: str, path: list[str], path_set: set[str]) -> None:
            if node in path_set:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = tuple([*path[cycle_start:], node])
                if cycle not in cycles:
                    cycles.append(cycle)
                return

            if node in visited or node not in graph:
                return

            visited.add(node)
            path.append(node)
            path_set.add(node)

            for dep in sorted(graph.get(node, [])):  # sorted for determinism
                if dep in candidates or dep in path_set:
                    dfs(dep, path, path_set)

            path.pop()
            path_set.remove(node)

        for start in sorted(candidates):
            if start not in visited:
                dfs(start, [], set())

        return cycles

    def activate_all(self) -> ActivationPlan:
        """Activate all registered plugins in dependency order.

        Computes the activation plan and activates plugins in order.
        If a plugin fails, subsequent dependent plugins are blocked.

        Returns:
            ActivationPlan reflecting the final state after activation attempts.
        """
        self._check_not_in_hook()

        with self._lock:
            plan = self._compute_activation_plan()

            # Track additional blocks from activation failures
            runtime_blocked: dict[str, str] = dict(plan.blocked)
            activated: list[str] = []

            for plugin_id in plan.order:
                # Skip if blocked at runtime (due to earlier failure)
                if plugin_id in runtime_blocked:
                    continue

                # Check if any hard dependency failed during this activation run
                manifest = self._plugins[plugin_id][0]
                dep_failed = False
                for dep in manifest.requires:
                    if dep in runtime_blocked:
                        runtime_blocked[plugin_id] = f"dependency '{dep}' failed to activate"
                        dep_failed = True
                        break

                if dep_failed:
                    continue

                try:
                    # Activate the plugin (uses internal implementation to avoid re-locking)
                    self._activate_internal(plugin_id)
                    activated.append(plugin_id)
                except Exception as e:
                    # Mark as blocked due to activation failure
                    runtime_blocked[plugin_id] = f"activation failed: {e}"
                    # The lifecycle.fail() was already called in _activate_internal

            # Return updated plan reflecting what actually happened
            return ActivationPlan(
                order=tuple(activated),
                blocked=runtime_blocked,
                cycles=plan.cycles,
            )

    def _activate_internal(self, plugin_id: str) -> None:
        """Internal activation (caller must hold lock, no re-entrancy check)."""
        manifest, lifecycle = self._plugins[plugin_id]

        if self._loader is None:
            raise RuntimeError("No loader configured - cannot activate plugins")

        # Begin activation (READY -> STARTING)
        lifecycle.begin_activation()

        try:
            # Load and instantiate the plugin
            plugin_instance = self._loader.load_entrypoint(manifest.entrypoint)
            lifecycle.instance = plugin_instance

            # Call activate() if the plugin has it
            if hasattr(plugin_instance, "activate"):
                plugin_instance.activate({})

            # Register slot contributions
            for slot_contrib in manifest.contributions.slots:
                self._slot_contributions[slot_contrib.slot_key].append(slot_contrib)
                # Re-sort by priority (descending) and tie-breakers (ascending)
                self._slot_contributions[slot_contrib.slot_key].sort(
                    key=lambda c: (-c.priority, c.plugin_id, c.contribution_id)
                )

            # Register hook contributions (track locally and with router)
            for hook_contrib in manifest.contributions.hooks:
                self._hook_contributions[hook_contrib.hook_key].append(hook_contrib)
                # Re-sort by priority (descending) and tie-breakers (ascending)
                self._hook_contributions[hook_contrib.hook_key].sort(
                    key=lambda c: (-c.priority, c.plugin_id, c.contribution_id)
                )
                # Also register with router for dispatch
                if self._hook_router is not None:
                    handler = self._loader.load_callable(hook_contrib.handler)
                    self._hook_router.register_handler(hook_contrib.hook_key, hook_contrib, handler)

            # Complete activation (STARTING -> ACTIVE)
            lifecycle.complete_activation()

        except Exception:
            # Rollback partial registrations on failure
            self._unregister_contributions(plugin_id, manifest)
            lifecycle.rollback()
            raise

    # =========================================================================
    # Resolution
    # =========================================================================

    def resolve_slot(
        self,
        slot_key: str,
        context: dict[str, Any] | None = None,
    ) -> list[Contribution]:
        """Resolve contributions for a slot.

        Args:
            slot_key: The slot to resolve.
            context: Optional context for filtering (not used in V1).

        Returns:
            List of contributions, ordered by priority (highest first),
            then by plugin_id and contribution_id for tie-breaking.
            For SINGLE policy slots, returns at most one contribution.

        Raises:
            SlotNotFoundError: If the slot is not defined.
        """
        with self._lock:
            if slot_key not in self._slots:
                raise SlotNotFoundError(slot_key)

            slot_def = self._slots[slot_key]
            contributions = self._slot_contributions[slot_key]

            # Filter to only active plugins
            active_contributions = [
                c
                for c in contributions
                if c.plugin_id in self._plugins
                and self._plugins[c.plugin_id][1].state == PluginState.ACTIVE
            ]

            # Apply slot policy
            if slot_def.policy == SlotPolicy.SINGLE and active_contributions:
                return [active_contributions[0]]

            return list(active_contributions)

    # =========================================================================
    # Hook Emission
    # =========================================================================

    def emit(
        self,
        hook_key: str,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> list[Any] | Any | None:
        """Emit an event to hook handlers.

        Args:
            hook_key: The hook to emit to.
            payload: The event payload.
            context: Optional context dict.

        Returns:
            For BROADCAST policy: list of all return values.
            For FIRST_RESULT policy: first non-None result, or None.

        Raises:
            HookNotFoundError: If the hook is not defined.
            RuntimeError: If no hook router is configured.
        """
        with self._lock:
            if hook_key not in self._hooks:
                raise HookNotFoundError(hook_key)

            if self._hook_router is None:
                raise RuntimeError("No hook router configured - cannot emit hooks")

            hook_def = self._hooks[hook_key]
            policy = hook_def.effective_policy

            # Set re-entrancy flag
            self._in_hook_emission.active = True
            try:
                return self._hook_router.emit(hook_key, policy, payload, context)
            finally:
                self._in_hook_emission.active = False

    # =========================================================================
    # Introspection
    # =========================================================================

    def runtime_info(self) -> RuntimeInfo:
        """Get summary information about the runtime.

        Returns a lightweight overview of the framework state including
        version information and counts. This method never throws.

        Returns:
            RuntimeInfo with framework metadata and counts.
        """
        # Get framework version from package metadata
        try:
            framework_version = importlib.metadata.version("switchboard")
        except importlib.metadata.PackageNotFoundError:
            # Fallback for development/testing when not installed as package
            framework_version = SWITCHBOARD_VERSION.__str__()

        # Get Python version
        python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )

        with self._lock:
            plugin_count = len(self._plugins)
            active_plugin_count = sum(
                1
                for _, lifecycle in self._plugins.values()
                if lifecycle.state == PluginState.ACTIVE
            )
            slot_count = len(self._slots)
            hook_count = len(self._hooks)

        return RuntimeInfo(
            framework_version=framework_version,
            python_version=python_version,
            plugin_count=plugin_count,
            active_plugin_count=active_plugin_count,
            slot_count=slot_count,
            hook_count=hook_count,
        )

    def snapshot(self) -> RuntimeSnapshot:
        """Capture a complete snapshot of the runtime state.

        Returns a point-in-time view of all plugins, slots, hooks, and
        their contributions. Useful for debugging, logging, and diagnostics.

        The timestamp is timezone-aware (UTC).

        Returns:
            RuntimeSnapshot with complete runtime state.
        """
        timestamp = datetime.now(UTC)
        runtime = self.runtime_info()

        with self._lock:
            # Build plugin snapshots
            plugin_snapshots: list[PluginSnapshot] = []
            for plugin_id, (manifest, lifecycle) in sorted(self._plugins.items()):
                # Collect all contribution IDs for this plugin
                contrib_ids: list[str] = []
                for slot_contrib in manifest.contributions.slots:
                    contrib_ids.append(slot_contrib.contribution_id)
                for hook_contrib in manifest.contributions.hooks:
                    contrib_ids.append(hook_contrib.contribution_id)

                plugin_snapshots.append(
                    PluginSnapshot(
                        plugin_id=plugin_id,
                        version=str(manifest.plugin_version),
                        state=lifecycle.state.value,
                        contributions=tuple(sorted(contrib_ids)),
                    )
                )

            # Build slot snapshots
            slot_snapshots: list[SlotSnapshot] = []
            for slot_key in sorted(self._slots.keys()):
                slot_def = self._slots[slot_key]
                contributions = self._slot_contributions[slot_key]

                # Filter to only active plugins' contributions
                active_contribs = [
                    ContributionSnapshot(
                        contribution_id=c.contribution_id,
                        plugin_id=c.plugin_id,
                        priority=c.priority,
                    )
                    for c in contributions
                    if c.plugin_id in self._plugins
                    and self._plugins[c.plugin_id][1].state == PluginState.ACTIVE
                ]

                slot_snapshots.append(
                    SlotSnapshot(
                        slot_key=slot_key,
                        policy=slot_def.policy.value,
                        contributions=tuple(active_contribs),
                    )
                )

            # Build hook snapshots
            hook_snapshots: list[HookSnapshot] = []
            for hook_key in sorted(self._hooks.keys()):
                hook_def = self._hooks[hook_key]
                hook_contribs = self._hook_contributions[hook_key]

                # Filter to only active plugins' contributions
                active_handlers = [
                    ContributionSnapshot(
                        contribution_id=c.contribution_id,
                        plugin_id=c.plugin_id,
                        priority=c.priority,
                    )
                    for c in hook_contribs
                    if c.plugin_id in self._plugins
                    and self._plugins[c.plugin_id][1].state == PluginState.ACTIVE
                ]

                hook_snapshots.append(
                    HookSnapshot(
                        hook_key=hook_key,
                        kind=hook_def.kind.value,
                        policy=hook_def.effective_policy.value,
                        handlers=tuple(active_handlers),
                    )
                )

        return RuntimeSnapshot(
            timestamp=timestamp,
            runtime=runtime,
            plugins=tuple(plugin_snapshots),
            slots=tuple(slot_snapshots),
            hooks=tuple(hook_snapshots),
        )

    def dump_state(self, format: Literal["text", "json"] = "text") -> str:
        """Dump the runtime state as a string.

        Produces a human-readable text format (default) or JSON for tooling.
        Output is deterministic (sorted keys, stable ordering) for meaningful diffs.

        Args:
            format: Output format - "text" for human-readable, "json" for tooling.

        Returns:
            String representation of the runtime state.
        """
        snap = self.snapshot()

        if format == "json":
            return self._dump_json(snap)
        return self._dump_text(snap)

    def _dump_json(self, snap: RuntimeSnapshot) -> str:
        """Serialize snapshot to JSON with deterministic ordering."""
        data = {
            "timestamp": snap.timestamp.isoformat(),
            "runtime": {
                "framework_version": snap.runtime.framework_version,
                "python_version": snap.runtime.python_version,
                "plugin_count": snap.runtime.plugin_count,
                "active_plugin_count": snap.runtime.active_plugin_count,
                "slot_count": snap.runtime.slot_count,
                "hook_count": snap.runtime.hook_count,
            },
            "plugins": [
                {
                    "plugin_id": p.plugin_id,
                    "version": p.version,
                    "state": p.state,
                    "contributions": list(p.contributions),
                }
                for p in snap.plugins
            ],
            "slots": [
                {
                    "slot_key": s.slot_key,
                    "policy": s.policy,
                    "contributions": [
                        {
                            "contribution_id": c.contribution_id,
                            "plugin_id": c.plugin_id,
                            "priority": c.priority,
                        }
                        for c in s.contributions
                    ],
                }
                for s in snap.slots
            ],
            "hooks": [
                {
                    "hook_key": h.hook_key,
                    "kind": h.kind,
                    "policy": h.policy,
                    "handlers": [
                        {
                            "contribution_id": c.contribution_id,
                            "plugin_id": c.plugin_id,
                            "priority": c.priority,
                        }
                        for c in h.handlers
                    ],
                }
                for h in snap.hooks
            ],
        }
        return json.dumps(data, indent=2, sort_keys=True)

    def _dump_text(self, snap: RuntimeSnapshot) -> str:
        """Format snapshot as human-readable text."""
        lines: list[str] = []

        # Header
        lines.append("=== Switchboard Runtime State ===")
        lines.append(f"Timestamp: {snap.timestamp.isoformat()}")
        lines.append("")

        # Runtime info
        lines.append("Runtime:")
        lines.append(f"  Framework: {snap.runtime.framework_version}")
        lines.append(f"  Python: {snap.runtime.python_version}")
        lines.append(
            f"  Plugins: {snap.runtime.active_plugin_count}/{snap.runtime.plugin_count} active"
        )
        lines.append(f"  Slots: {snap.runtime.slot_count}")
        lines.append(f"  Hooks: {snap.runtime.hook_count}")
        lines.append("")

        # Plugins
        lines.append("Plugins:")
        if snap.plugins:
            for p in snap.plugins:
                status = f"[{p.state}]"
                lines.append(f"  {p.plugin_id} v{p.version} {status}")
                if p.contributions:
                    lines.append(f"    contributions: {', '.join(p.contributions)}")
        else:
            lines.append("  (none)")
        lines.append("")

        # Slots
        lines.append("Slots:")
        for s in snap.slots:
            lines.append(f"  {s.slot_key} ({s.policy})")
            if s.contributions:
                for c in s.contributions:
                    lines.append(f"    - {c.contribution_id} from {c.plugin_id} (pri={c.priority})")
            else:
                lines.append("    (no contributions)")
        lines.append("")

        # Hooks
        lines.append("Hooks:")
        for h in snap.hooks:
            lines.append(f"  {h.hook_key} ({h.kind}, {h.policy})")
            if h.handlers:
                for c in h.handlers:
                    lines.append(f"    - {c.contribution_id} from {c.plugin_id} (pri={c.priority})")
            else:
                lines.append("    (no handlers)")

        return "\n".join(lines)

    def get_plugin_state(self, plugin_id: str) -> PluginState:
        """Get the current lifecycle state of a plugin.

        Args:
            plugin_id: The plugin to query.

        Returns:
            The plugin's current state.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)
            return self._plugins[plugin_id][1].state

    def list_plugins(self) -> list[str]:
        """List all registered plugin IDs."""
        with self._lock:
            return list(self._plugins.keys())

    def list_slots(self) -> list[str]:
        """List all defined slot keys."""
        return list(self._slots.keys())

    def list_hooks(self) -> list[str]:
        """List all defined hook keys."""
        return list(self._hooks.keys())

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _check_not_in_hook(self) -> None:
        """Raise if called from within a hook handler."""
        if getattr(self._in_hook_emission, "active", False):
            raise LifecycleError(
                "PatchPanel",
                "mutate registry",
                "in_hook_emission",
            )
