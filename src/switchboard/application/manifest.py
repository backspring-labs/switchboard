"""Manifest parsing and loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from switchboard.domain.errors import ManifestError
from switchboard.domain.models import (
    ApiRange,
    HookContribution,
    ManifestContributions,
    PluginManifest,
    SemVer,
    SlotContribution,
)


def parse_manifest(yaml_str: str) -> PluginManifest:
    """Parse a YAML string into a PluginManifest.

    Args:
        yaml_str: YAML-formatted manifest string.

    Returns:
        Parsed PluginManifest object.

    Raises:
        ManifestError: If the YAML is invalid or required fields are missing.
    """
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a YAML mapping")

    return _parse_manifest_dict(data)


def load_manifest(path: str | Path) -> PluginManifest:
    """Load a manifest from a file path.

    Args:
        path: Path to the manifest YAML file.

    Returns:
        Parsed PluginManifest object.

    Raises:
        ManifestError: If the file cannot be read or parsed.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ManifestError(f"Cannot read manifest file: {e}") from e

    return parse_manifest(content)


def _parse_manifest_dict(data: dict[str, Any]) -> PluginManifest:
    """Parse a dictionary into a PluginManifest.

    Args:
        data: Dictionary parsed from YAML.

    Returns:
        PluginManifest object.

    Raises:
        ManifestError: If required fields are missing or invalid.
    """
    # Required fields
    manifest_version = _require_field(data, "manifest_version", str)
    plugin_id = _require_field(data, "plugin_id", str)
    plugin_version_str = _require_field(data, "plugin_version", str)
    requires_switchboard_str = _require_field(data, "requires_switchboard", str)
    entrypoint = _require_field(data, "entrypoint", str)

    # Parse version and range
    try:
        plugin_version = SemVer.parse(plugin_version_str)
    except ValueError as e:
        raise ManifestError(f"Invalid plugin_version: {e}") from e

    try:
        requires_switchboard = ApiRange.parse(requires_switchboard_str)
    except ValueError as e:
        raise ManifestError(f"Invalid requires_switchboard: {e}") from e

    # Optional fields
    name = data.get("name", "")
    description = data.get("description", "")

    # Parse contributions
    contributions = _parse_contributions(data.get("contributions", {}), plugin_id)

    # Parse dependency declarations (V2)
    requires = _parse_string_list(data.get("requires", []), "requires")
    optional_requires = _parse_string_list(data.get("optional_requires", []), "optional_requires")

    return PluginManifest(
        manifest_version=manifest_version,
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        requires_switchboard=requires_switchboard,
        entrypoint=entrypoint,
        name=name,
        description=description,
        contributions=contributions,
        requires=requires,
        optional_requires=optional_requires,
    )


def _require_field(data: dict[str, Any], field: str, expected_type: type) -> Any:
    """Extract a required field from the manifest data.

    Args:
        data: The manifest dictionary.
        field: The field name to extract.
        expected_type: The expected type of the field value.

    Returns:
        The field value.

    Raises:
        ManifestError: If the field is missing or has wrong type.
    """
    if field not in data:
        raise ManifestError(f"Missing required field: {field}")

    value = data[field]
    if not isinstance(value, expected_type):
        raise ManifestError(
            f"Field '{field}' must be {expected_type.__name__}, got {type(value).__name__}"
        )

    return value


def _parse_string_list(data: list[str] | None, field_name: str) -> tuple[str, ...]:
    """Parse a list of strings from manifest data.

    Args:
        data: List of strings (may be None or empty).
        field_name: Name of the field (for error messages).

    Returns:
        Tuple of strings.

    Raises:
        ManifestError: If data is not a list of strings.
    """
    if data is None:
        return ()

    if not isinstance(data, list):
        raise ManifestError(f"{field_name} must be a list")

    for i, item in enumerate(data):
        if not isinstance(item, str):
            raise ManifestError(f"{field_name}[{i}] must be a string, got {type(item).__name__}")

    return tuple(data)


def _parse_contributions(data: dict[str, Any] | None, plugin_id: str) -> ManifestContributions:
    """Parse the contributions section of a manifest.

    Args:
        data: The contributions dictionary (may be None or empty).
        plugin_id: The plugin ID (used for contribution objects).

    Returns:
        ManifestContributions object.

    Raises:
        ManifestError: If contribution data is invalid.
    """
    if not data:
        return ManifestContributions()

    if not isinstance(data, dict):
        raise ManifestError("contributions must be a mapping")

    slots = _parse_slot_contributions(data.get("slots", []), plugin_id)
    hooks = _parse_hook_contributions(data.get("hooks", []), plugin_id)

    return ManifestContributions(slots=slots, hooks=hooks)


def _parse_slot_contributions(
    data: list[dict[str, Any]], plugin_id: str
) -> tuple[SlotContribution, ...]:
    """Parse slot contributions from manifest data.

    Args:
        data: List of slot contribution dictionaries.
        plugin_id: The owning plugin ID.

    Returns:
        Tuple of SlotContribution objects.

    Raises:
        ManifestError: If contribution data is invalid.
    """
    if not isinstance(data, list):
        raise ManifestError("contributions.slots must be a list")

    contributions = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ManifestError(f"contributions.slots[{i}] must be a mapping")

        try:
            contrib = SlotContribution(
                plugin_id=plugin_id,
                contribution_id=_require_field(item, "contribution_id", str),
                slot_key=_require_field(item, "slot_key", str),
                priority=item.get("priority", 50),
                factory=item.get("factory", ""),
                metadata=item.get("metadata", {}),
            )
            contributions.append(contrib)
        except (ValueError, TypeError) as e:
            raise ManifestError(f"Invalid slot contribution [{i}]: {e}") from e

    return tuple(contributions)


def _parse_hook_contributions(
    data: list[dict[str, Any]], plugin_id: str
) -> tuple[HookContribution, ...]:
    """Parse hook contributions from manifest data.

    Args:
        data: List of hook contribution dictionaries.
        plugin_id: The owning plugin ID.

    Returns:
        Tuple of HookContribution objects.

    Raises:
        ManifestError: If contribution data is invalid.
    """
    if not isinstance(data, list):
        raise ManifestError("contributions.hooks must be a list")

    contributions = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ManifestError(f"contributions.hooks[{i}] must be a mapping")

        try:
            contrib = HookContribution(
                plugin_id=plugin_id,
                contribution_id=_require_field(item, "contribution_id", str),
                hook_key=_require_field(item, "hook_key", str),
                priority=item.get("priority", 50),
                handler=item.get("handler", ""),
                metadata=item.get("metadata", {}),
            )
            contributions.append(contrib)
        except (ValueError, TypeError) as e:
            raise ManifestError(f"Invalid hook contribution [{i}]: {e}") from e

    return tuple(contributions)
