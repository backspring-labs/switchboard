"""In-memory hook router - simple implementation without Pluggy."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from switchboard.domain.models import HookContribution, HookPolicy

logger = logging.getLogger(__name__)


@dataclass
class RegisteredHandler:
    """A handler registered for a hook."""

    contribution_id: str
    plugin_id: str
    priority: int
    handler: Callable[..., Any]


class MemoryHookRouter:
    """Simple in-memory hook router implementing HookRouterPort.

    This implementation stores handlers in a dictionary and dispatches
    according to the specified policy (broadcast or first_result).
    """

    def __init__(self) -> None:
        # hook_key -> list of registered handlers
        self._handlers: dict[str, list[RegisteredHandler]] = {}

    def register_handler(
        self,
        hook_key: str,
        contribution: HookContribution,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for a hook."""
        if hook_key not in self._handlers:
            self._handlers[hook_key] = []

        registered = RegisteredHandler(
            contribution_id=contribution.contribution_id,
            plugin_id=contribution.plugin_id,
            priority=contribution.priority,
            handler=handler,
        )
        self._handlers[hook_key].append(registered)

        # Sort by priority (descending), then plugin_id, then contribution_id
        self._handlers[hook_key].sort(
            key=lambda h: (-h.priority, h.plugin_id, h.contribution_id)
        )

    def unregister_handler(self, hook_key: str, contribution_id: str) -> None:
        """Unregister a handler from a hook."""
        if hook_key not in self._handlers:
            return

        self._handlers[hook_key] = [
            h for h in self._handlers[hook_key] if h.contribution_id != contribution_id
        ]

    def emit(
        self,
        hook_key: str,
        policy: HookPolicy,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> list[Any] | Any | None:
        """Emit an event to all registered handlers.

        Args:
            hook_key: The hook to emit to.
            policy: The dispatch policy (BROADCAST or FIRST_RESULT).
            payload: The event payload.
            context: Optional context dict.

        Returns:
            For BROADCAST: list of all return values.
            For FIRST_RESULT: first non-None result, or None.
        """
        from switchboard.domain.models import HookPolicy

        handlers = self._handlers.get(hook_key, [])

        if not handlers:
            if policy == HookPolicy.FIRST_RESULT:
                return None
            return []

        ctx = context or {}

        if policy == HookPolicy.BROADCAST:
            return self._emit_broadcast(handlers, payload, ctx)
        else:  # FIRST_RESULT
            return self._emit_first_result(handlers, payload, ctx)

    def _emit_broadcast(
        self,
        handlers: list[RegisteredHandler],
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> list[Any]:
        """Call all handlers, collecting results. Continue on errors."""
        results: list[Any] = []

        for registered in handlers:
            try:
                result = registered.handler(payload, context)
                results.append(result)
            except Exception:
                logger.exception(
                    "Handler %s from plugin %s raised an exception",
                    registered.contribution_id,
                    registered.plugin_id,
                )
                # Continue to next handler

        return results

    def _emit_first_result(
        self,
        handlers: list[RegisteredHandler],
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> Any | None:
        """Call handlers until one returns a non-None result."""
        for registered in handlers:
            try:
                result = registered.handler(payload, context)
                if result is not None:
                    return result
            except Exception:
                logger.exception(
                    "Handler %s from plugin %s raised an exception",
                    registered.contribution_id,
                    registered.plugin_id,
                )
                # Propagate exception for first_result policy
                raise

        return None

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()
