"""Sample plugin for testing."""

from __future__ import annotations

from typing import Any


class SamplePlugin:
    """A sample plugin that tracks its lifecycle."""

    def __init__(self) -> None:
        self.activated = False
        self.deactivated = False
        self.activate_context: dict[str, Any] | None = None
        self.deactivate_context: dict[str, Any] | None = None

    def activate(self, context: dict[str, Any]) -> None:
        """Called when the plugin is activated."""
        self.activated = True
        self.activate_context = context

    def deactivate(self, context: dict[str, Any]) -> None:
        """Called when the plugin is deactivated."""
        self.deactivated = True
        self.deactivate_context = context


class AnotherPlugin:
    """Another sample plugin for multi-plugin tests."""

    def __init__(self) -> None:
        self.activated = False

    def activate(self, context: dict[str, Any]) -> None:
        self.activated = True


# Sample hook handlers
def on_app_started(payload: dict[str, Any], context: dict[str, Any]) -> str:
    """Handler for app.started event."""
    return f"started:{payload.get('timestamp', 0)}"


def on_app_started_high_priority(payload: dict[str, Any], context: dict[str, Any]) -> str:
    """High priority handler for app.started event."""
    return f"high:{payload.get('timestamp', 0)}"


def command_handler(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
    """Handler for command hook - returns result for matching commands."""
    if payload.get("command") == "greet":
        return {"greeting": f"Hello, {payload.get('name', 'world')}!"}
    return None


def command_handler_fallback(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Fallback command handler."""
    return {"error": "Unknown command"}


# Sample factory for slot contributions
def build_sidebar_widget() -> dict[str, Any]:
    """Factory that builds a sidebar widget descriptor."""
    return {"type": "sidebar", "title": "Sample Widget"}
