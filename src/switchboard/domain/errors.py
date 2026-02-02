"""Switchboard domain exceptions."""

from __future__ import annotations


class SwitchboardError(Exception):
    """Base exception for all Switchboard errors."""


class PluginNotFoundError(SwitchboardError):
    """Raised when a plugin is not found in the registry."""

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin not found: {plugin_id}")


class SlotNotFoundError(SwitchboardError):
    """Raised when a slot is not found in the registry."""

    def __init__(self, slot_key: str) -> None:
        self.slot_key = slot_key
        super().__init__(f"Slot not found: {slot_key}")


class HookNotFoundError(SwitchboardError):
    """Raised when a hook is not found in the registry."""

    def __init__(self, hook_key: str) -> None:
        self.hook_key = hook_key
        super().__init__(f"Hook not found: {hook_key}")


class CompatibilityError(SwitchboardError):
    """Raised when a plugin is incompatible with the current Switchboard version."""

    def __init__(self, plugin_id: str, required: str, current: str) -> None:
        self.plugin_id = plugin_id
        self.required = required
        self.current = current
        super().__init__(
            f"Plugin {plugin_id} requires switchboard {required}, but {current} is installed"
        )


class LifecycleError(SwitchboardError):
    """Raised when a lifecycle operation is invalid for the current state."""

    def __init__(self, plugin_id: str, operation: str, current_state: str) -> None:
        self.plugin_id = plugin_id
        self.operation = operation
        self.current_state = current_state
        super().__init__(
            f"Cannot {operation} plugin {plugin_id}: currently in state '{current_state}'"
        )


class DuplicateRegistrationError(SwitchboardError):
    """Raised when attempting to register a plugin that is already registered."""

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin already registered: {plugin_id}")


class ManifestError(SwitchboardError):
    """Raised when a plugin manifest is invalid."""

    def __init__(self, message: str, plugin_id: str | None = None) -> None:
        self.plugin_id = plugin_id
        prefix = f"Plugin {plugin_id}: " if plugin_id else ""
        super().__init__(f"{prefix}{message}")


class ContributionError(SwitchboardError):
    """Raised when a contribution is invalid or cannot be registered."""

    def __init__(self, message: str, contribution_id: str | None = None) -> None:
        self.contribution_id = contribution_id
        prefix = f"Contribution {contribution_id}: " if contribution_id else ""
        super().__init__(f"{prefix}{message}")
