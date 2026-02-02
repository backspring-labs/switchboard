"""Switchboard PatchPanel - the central registry and resolver."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

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
    Contribution,
    HookDefinition,
    PluginManifest,
    SemVer,
    SlotContribution,
    SlotDefinition,
    SlotPolicy,
)

if TYPE_CHECKING:
    from switchboard.domain.ports import HookRouterPort, LoaderPort

# Current Switchboard version for compatibility checks
SWITCHBOARD_VERSION = SemVer.parse("0.1.0")


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

            if self._loader is None:
                raise RuntimeError("No loader configured - cannot activate plugins")

            manifest, lifecycle = self._plugins[plugin_id]

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

                # Register hook handlers with router
                if self._hook_router is not None:
                    for hook_contrib in manifest.contributions.hooks:
                        handler = self._loader.load_callable(hook_contrib.handler)
                        self._hook_router.register_handler(
                            hook_contrib.hook_key, hook_contrib, handler
                        )

                # Complete activation (STARTING -> ACTIVE)
                lifecycle.complete_activation()

            except Exception:
                # Rollback partial registrations on failure
                self._unregister_contributions(plugin_id, manifest)
                lifecycle.rollback()
                raise

    def _unregister_contributions(
        self, plugin_id: str, manifest: PluginManifest
    ) -> None:
        """Unregister all contributions for a plugin.

        This is used during deactivation and rollback to clean up
        slot contributions and hook handlers.

        Args:
            plugin_id: The plugin whose contributions to remove.
            manifest: The plugin's manifest (for contribution list).
        """
        # Unregister hook handlers
        if self._hook_router is not None:
            for hook_contrib in manifest.contributions.hooks:
                self._hook_router.unregister_handler(
                    hook_contrib.hook_key, hook_contrib.contribution_id
                )

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
