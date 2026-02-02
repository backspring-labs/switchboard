"""Plugin loader adapter - imports and instantiates plugins."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class ImportLoader:
    """Loader that imports plugin entrypoints using Python's import system.

    Entrypoint format: 'module.path:ClassName' or 'module.path:function_name'
    """

    def load_entrypoint(self, entrypoint: str) -> Any:
        """Load and instantiate a plugin from its entrypoint string.

        Args:
            entrypoint: Import path in format 'module.path:ClassName'.

        Returns:
            The instantiated plugin object.

        Raises:
            ValueError: If the entrypoint format is invalid.
            ImportError: If the module cannot be imported.
            AttributeError: If the class cannot be found.
        """
        module_path, class_name = self._parse_entrypoint(entrypoint)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()

    def load_callable(self, import_path: str) -> Callable[..., Any]:
        """Load a callable (function or class) from an import path.

        Args:
            import_path: Import path in format 'module.path:name'.

        Returns:
            The callable.

        Raises:
            ValueError: If the import path format is invalid.
            ImportError: If the module cannot be imported.
            AttributeError: If the name cannot be found.
        """
        module_path, name = self._parse_entrypoint(import_path)
        module = importlib.import_module(module_path)
        return getattr(module, name)  # type: ignore[no-any-return]

    def _parse_entrypoint(self, entrypoint: str) -> tuple[str, str]:
        """Parse an entrypoint string into module path and name."""
        if ":" not in entrypoint:
            raise ValueError(
                f"Invalid entrypoint format: {entrypoint!r} (expected 'module.path:name')"
            )
        parts = entrypoint.split(":", 1)
        if not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid entrypoint format: {entrypoint!r} (expected 'module.path:name')"
            )
        return parts[0], parts[1]
