"""Switchboard plugin lifecycle state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from transitions import Machine

from switchboard.domain.errors import LifecycleError


class PluginState(Enum):
    """Plugin lifecycle states."""

    READY = "ready"  # Registered, validated, not running
    STARTING = "starting"  # Activation in progress
    ACTIVE = "active"  # Running, contributions invocable
    STOPPING = "stopping"  # Deactivation in progress
    FAILED = "failed"  # Quarantined due to error


# State invariants (documented for reference, enforced by transition guards):
#
# READY:
#   - Manifest parsed and validated
#   - requires_switchboard compatibility verified
#   - Plugin registered in PatchPanel registry
#   - Contributions declared but NOT active
#   - Entrypoint NOT yet imported
#
# STARTING:
#   - Entrypoint being imported
#   - Plugin instance being constructed
#   - Contributions being registered with router
#   - On failure: rollback to READY or transition to FAILED
#
# ACTIVE:
#   - Plugin instance exists and activate() was called
#   - All contributions registered and resolvable
#   - Hook handlers wired and invocable
#
# STOPPING:
#   - deactivate() called on plugin instance
#   - Contributions being unregistered
#   - Hook handlers being unwired
#   - On completion: return to READY
#
# FAILED:
#   - Plugin is quarantined
#   - last_error stored
#   - Contributions NOT resolvable
#   - Hook handlers NOT invocable


@dataclass
class PluginLifecycle:
    """Manages the lifecycle state of a single plugin."""

    plugin_id: str
    # transitions library will set this attribute directly (as a string)
    _state_str: str = field(default=PluginState.READY.value, init=False)
    _instance: Any = field(default=None, init=False)
    _last_error: BaseException | None = field(default=None, init=False)
    _machine: Machine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the state machine."""
        self._machine = Machine(
            model=self,
            states=[s.value for s in PluginState],
            initial=PluginState.READY.value,
            auto_transitions=False,
            send_event=True,
            model_attribute="_state_str",
        )

        # Define transitions
        self._machine.add_transition(
            trigger="_do_start",
            source=PluginState.READY.value,
            dest=PluginState.STARTING.value,
        )
        self._machine.add_transition(
            trigger="_do_activate",
            source=PluginState.STARTING.value,
            dest=PluginState.ACTIVE.value,
        )
        self._machine.add_transition(
            trigger="_do_stop",
            source=PluginState.ACTIVE.value,
            dest=PluginState.STOPPING.value,
        )
        self._machine.add_transition(
            trigger="_do_ready",
            source=PluginState.STOPPING.value,
            dest=PluginState.READY.value,
        )
        self._machine.add_transition(
            trigger="_do_fail",
            source=[PluginState.STARTING.value, PluginState.ACTIVE.value],
            dest=PluginState.FAILED.value,
        )
        self._machine.add_transition(
            trigger="_do_reset",
            source=PluginState.FAILED.value,
            dest=PluginState.READY.value,
        )
        # Allow rollback from starting to ready on activation failure
        self._machine.add_transition(
            trigger="_do_rollback",
            source=PluginState.STARTING.value,
            dest=PluginState.READY.value,
        )

    @property
    def state(self) -> PluginState:
        """Current lifecycle state."""
        return PluginState(self._state_str)

    @property
    def instance(self) -> Any:
        """The plugin instance (only valid when ACTIVE)."""
        return self._instance

    @instance.setter
    def instance(self, value: Any) -> None:
        """Set the plugin instance."""
        self._instance = value

    @property
    def last_error(self) -> BaseException | None:
        """The last error that caused a failure."""
        return self._last_error

    @property
    def is_active(self) -> bool:
        """Check if the plugin is in the ACTIVE state."""
        return self.state == PluginState.ACTIVE

    @property
    def is_failed(self) -> bool:
        """Check if the plugin is in the FAILED state."""
        return self.state == PluginState.FAILED

    def begin_activation(self) -> None:
        """Transition from READY to STARTING."""
        if self.state != PluginState.READY:
            raise LifecycleError(self.plugin_id, "activate", self.state.value)
        self._do_start()  # type: ignore[attr-defined]

    def complete_activation(self) -> None:
        """Transition from STARTING to ACTIVE."""
        if self.state != PluginState.STARTING:
            raise LifecycleError(self.plugin_id, "complete activation", self.state.value)
        self._do_activate()  # type: ignore[attr-defined]

    def begin_deactivation(self) -> None:
        """Transition from ACTIVE to STOPPING."""
        if self.state != PluginState.ACTIVE:
            raise LifecycleError(self.plugin_id, "deactivate", self.state.value)
        self._do_stop()  # type: ignore[attr-defined]

    def complete_deactivation(self) -> None:
        """Transition from STOPPING to READY."""
        if self.state != PluginState.STOPPING:
            raise LifecycleError(self.plugin_id, "complete deactivation", self.state.value)
        self._instance = None
        self._do_ready()  # type: ignore[attr-defined]

    def fail(self, error: BaseException) -> None:
        """Transition to FAILED state with an error."""
        if self.state not in (PluginState.STARTING, PluginState.ACTIVE):
            raise LifecycleError(self.plugin_id, "fail", self.state.value)
        self._last_error = error
        self._instance = None
        self._do_fail()  # type: ignore[attr-defined]

    def rollback(self) -> None:
        """Rollback from STARTING to READY (activation failed but not fatal)."""
        if self.state != PluginState.STARTING:
            raise LifecycleError(self.plugin_id, "rollback", self.state.value)
        self._instance = None
        self._do_rollback()  # type: ignore[attr-defined]

    def reset(self) -> None:
        """Reset from FAILED to READY (manual recovery)."""
        if self.state != PluginState.FAILED:
            raise LifecycleError(self.plugin_id, "reset", self.state.value)
        self._last_error = None
        self._do_reset()  # type: ignore[attr-defined]
