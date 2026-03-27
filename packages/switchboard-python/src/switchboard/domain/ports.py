"""Switchboard domain ports - interfaces for adapters."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from switchboard.domain.models import HookContribution, HookPolicy


class HookRouterPort(Protocol):
    """Port for hook dispatch - implemented by adapters (memory, pluggy, etc.)."""

    @abstractmethod
    def register_handler(
        self,
        hook_key: str,
        contribution: HookContribution,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for a hook.

        Args:
            hook_key: The hook to register for.
            contribution: The contribution metadata.
            handler: The callable to invoke.
        """
        ...

    @abstractmethod
    def unregister_handler(self, hook_key: str, contribution_id: str) -> None:
        """Unregister a handler from a hook.

        Args:
            hook_key: The hook to unregister from.
            contribution_id: The contribution ID to remove.
        """
        ...

    @abstractmethod
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
            policy: The dispatch policy (broadcast or first_result).
            payload: The event payload.
            context: Optional context dict.

        Returns:
            For BROADCAST: list of all return values.
            For FIRST_RESULT: first non-None result, or None.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all registered handlers."""
        ...


class LoaderPort(Protocol):
    """Port for loading plugin entrypoints - implemented by adapters."""

    @abstractmethod
    def load_entrypoint(self, entrypoint: str) -> Any:
        """Load and instantiate a plugin from its entrypoint string.

        Args:
            entrypoint: Import path in format 'module.path:ClassName'.

        Returns:
            The instantiated plugin object.

        Raises:
            ImportError: If the module cannot be imported.
            AttributeError: If the class cannot be found.
        """
        ...

    @abstractmethod
    def load_callable(self, import_path: str) -> Callable[..., Any]:
        """Load a callable (function or class) from an import path.

        Args:
            import_path: Import path in format 'module.path:name'.

        Returns:
            The callable.

        Raises:
            ImportError: If the module cannot be imported.
            AttributeError: If the name cannot be found.
        """
        ...
