"""Pluggy-based hook router adapter."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pluggy

if TYPE_CHECKING:
    from collections.abc import Callable

    from switchboard.domain.models import HookContribution, HookPolicy

logger = logging.getLogger(__name__)


@dataclass
class RegisteredHandler:
    """Metadata for a registered handler."""

    contribution_id: str
    plugin_id: str
    priority: int
    handler: Callable[..., Any]


@dataclass
class HookState:
    """State for a single hook managed by Pluggy."""

    pm: pluggy.PluginManager
    hook_name: str
    handlers: list[RegisteredHandler] = field(default_factory=list)


class PluggyHookRouter:
    """Hook router using Pluggy for dispatch.

    This adapter wraps Pluggy's plugin manager to implement the HookRouterPort
    protocol. It dynamically creates hookspecs and registers handlers.

    Key design decisions:
    - Each hook_key gets its own PluginManager for isolation
    - Priority is implemented by registering handlers in reverse priority order
      (Pluggy uses LIFO - last registered is called first)
    - first_result: Uses Pluggy's hook caller with firstresult=True
      (stops on first non-None result)
    - broadcast: Manual iteration to implement continue-on-error semantics
      (Pluggy propagates exceptions by default)
    """

    def __init__(self) -> None:
        self._hooks: dict[str, HookState] = {}
        self._wrapper_counter: int = 0  # Unique ID for wrapper classes

    def register_handler(
        self,
        hook_key: str,
        contribution: HookContribution,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for a hook."""
        if hook_key not in self._hooks:
            self._hooks[hook_key] = self._create_hook_state(hook_key)

        state = self._hooks[hook_key]

        registered = RegisteredHandler(
            contribution_id=contribution.contribution_id,
            plugin_id=contribution.plugin_id,
            priority=contribution.priority,
            handler=handler,
        )

        # Add to handlers list and re-sort
        state.handlers.append(registered)
        state.handlers.sort(key=lambda h: (-h.priority, h.plugin_id, h.contribution_id))

        # Rebuild Pluggy registrations in correct order
        self._rebuild_pluggy_registrations(state)

    def unregister_handler(self, hook_key: str, contribution_id: str) -> None:
        """Unregister a handler from a hook."""
        if hook_key not in self._hooks:
            return

        state = self._hooks[hook_key]

        # Remove from handlers list
        state.handlers = [
            h for h in state.handlers if h.contribution_id != contribution_id
        ]

        # Rebuild Pluggy registrations
        self._rebuild_pluggy_registrations(state)

    def emit(
        self,
        hook_key: str,
        policy: HookPolicy,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> list[Any] | Any | None:
        """Emit an event to all registered handlers using Pluggy."""
        from switchboard.domain.models import HookPolicy

        if hook_key not in self._hooks:
            if policy == HookPolicy.FIRST_RESULT:
                return None
            return []

        state = self._hooks[hook_key]

        if not state.handlers:
            if policy == HookPolicy.FIRST_RESULT:
                return None
            return []

        ctx = context or {}

        # Get the Pluggy hook caller
        hook_caller = getattr(state.pm.hook, state.hook_name)

        if policy == HookPolicy.FIRST_RESULT:
            # Use Pluggy's firstresult - it stops on first non-None result
            # which matches our semantics exactly
            return hook_caller(payload=payload, context=ctx)
        else:
            # Broadcast with continue-on-error semantics
            # Pluggy propagates exceptions, so we iterate manually to log and continue
            results: list[Any] = []
            for registered in state.handlers:
                try:
                    result = registered.handler(payload, ctx)
                    results.append(result)
                except Exception:
                    logger.exception(
                        "Handler %s from plugin %s raised an exception",
                        registered.contribution_id,
                        registered.plugin_id,
                    )
            return results

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._hooks.clear()

    def _create_hook_state(self, hook_key: str) -> HookState:
        """Create a new HookState with PluginManager for a hook."""
        hook_name = self._normalize_hook_name(hook_key)
        project_name = f"switchboard_{hook_name}"
        pm = pluggy.PluginManager(project_name)

        # Create and register hookspec
        hookspec_class = self._create_hookspec_class(project_name, hook_name)
        pm.add_hookspecs(hookspec_class)

        return HookState(pm=pm, hook_name=hook_name)

    def _create_hookspec_class(
        self, project_name: str, hook_name: str, firstresult: bool = True
    ) -> type:
        """Create a hookspec class for a hook.

        Args:
            project_name: Pluggy project name for marker
            hook_name: Normalized hook name (valid Python identifier)
            firstresult: If True, Pluggy stops on first non-None result
        """
        hookspec = pluggy.HookspecMarker(project_name)

        def hook_method(
            self: Any, payload: dict[str, Any], context: dict[str, Any]
        ) -> Any:
            """Hook specification method."""

        # Apply the hookspec decorator with firstresult for short-circuit behavior
        decorated = hookspec(hook_method, firstresult=firstresult)

        # Create the class
        return type(f"HookSpec_{hook_name}", (), {hook_name: decorated})

    def _rebuild_pluggy_registrations(self, state: HookState) -> None:
        """Rebuild all Pluggy registrations in priority order.

        Pluggy calls handlers in LIFO order (last registered = first called).
        So we register in reverse priority order: lowest priority first,
        highest priority last.
        """
        # Unregister all existing plugins (except the hookspec)
        for plugin in list(state.pm.get_plugins()):
            # The hookspec class is registered as a plugin too, skip it
            if hasattr(plugin, state.hook_name) and callable(
                getattr(plugin, state.hook_name, None)
            ):
                # Check if it's a hookspec (has the marker) vs hookimpl
                method = getattr(plugin, state.hook_name)
                if not hasattr(method, "hookimpl"):
                    continue
            with contextlib.suppress(ValueError):
                state.pm.unregister(plugin)

        # Register in reverse priority order (lowest first, highest last)
        # so Pluggy's LIFO ordering gives us highest-priority-first execution
        for registered in reversed(state.handlers):
            wrapper = self._create_wrapper(state, registered)
            state.pm.register(wrapper)

    def _create_wrapper(self, state: HookState, registered: RegisteredHandler) -> object:
        """Create a fresh wrapper plugin instance for a handler."""
        project_name = f"switchboard_{state.hook_name}"
        hookimpl = pluggy.HookimplMarker(project_name)

        handler = registered.handler

        def wrapper_method(
            self: Any, payload: dict[str, Any], context: dict[str, Any]
        ) -> Any:
            return handler(payload, context)

        # Mark as hookimpl
        wrapper_method.hookimpl = True  # type: ignore[attr-defined]
        decorated = hookimpl(wrapper_method)

        # Create wrapper class with unique name
        self._wrapper_counter += 1
        wrapper_class = type(
            f"Wrapper_{state.hook_name}_{self._wrapper_counter}",
            (),
            {state.hook_name: decorated},
        )
        return wrapper_class()

    def _normalize_hook_name(self, hook_key: str) -> str:
        """Convert a hook key to a valid Python identifier."""
        return hook_key.replace(".", "_").replace("-", "_")
