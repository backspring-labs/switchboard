"""Tests for manifest parsing."""

import tempfile
from pathlib import Path

import pytest

from switchboard import (
    HookContribution,
    ManifestError,
    SlotContribution,
    load_manifest,
    parse_manifest,
)


class TestParseManifest:
    """Tests for parse_manifest()."""

    def test_parse_minimal_manifest(self) -> None:
        """Parse a manifest with only required fields."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: my_plugin:MyPlugin
"""
        manifest = parse_manifest(yaml_str)

        assert manifest.manifest_version == "1"
        assert manifest.plugin_id == "com.example.test"
        assert str(manifest.plugin_version) == "1.0.0"
        assert manifest.entrypoint == "my_plugin:MyPlugin"
        assert manifest.name == ""
        assert manifest.description == ""
        assert manifest.contributions.slots == ()
        assert manifest.contributions.hooks == ()

    def test_parse_full_manifest(self) -> None:
        """Parse a manifest with all fields."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.full
plugin_version: "2.1.0"
requires_switchboard: ">=0.1.0"
entrypoint: full_plugin:FullPlugin
name: Full Plugin
description: A plugin with all fields
contributions:
  slots:
    - contribution_id: sidebar.widget
      slot_key: ui.sidebar
      priority: 75
      factory: full_plugin:SidebarWidget
      metadata:
        icon: star
  hooks:
    - contribution_id: on.started
      hook_key: app.started
      priority: 100
      handler: full_plugin:on_started
"""
        manifest = parse_manifest(yaml_str)

        assert manifest.plugin_id == "com.example.full"
        assert manifest.name == "Full Plugin"
        assert manifest.description == "A plugin with all fields"

        # Check slot contribution
        assert len(manifest.contributions.slots) == 1
        slot = manifest.contributions.slots[0]
        assert isinstance(slot, SlotContribution)
        assert slot.plugin_id == "com.example.full"
        assert slot.contribution_id == "sidebar.widget"
        assert slot.slot_key == "ui.sidebar"
        assert slot.priority == 75
        assert slot.factory == "full_plugin:SidebarWidget"
        assert slot.metadata == {"icon": "star"}

        # Check hook contribution
        assert len(manifest.contributions.hooks) == 1
        hook = manifest.contributions.hooks[0]
        assert isinstance(hook, HookContribution)
        assert hook.plugin_id == "com.example.full"
        assert hook.contribution_id == "on.started"
        assert hook.hook_key == "app.started"
        assert hook.priority == 100
        assert hook.handler == "full_plugin:on_started"

    def test_parse_multiple_contributions(self) -> None:
        """Parse a manifest with multiple contributions."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.multi
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: multi:Plugin
contributions:
  slots:
    - contribution_id: slot1
      slot_key: ui.sidebar
    - contribution_id: slot2
      slot_key: ui.toolbar
  hooks:
    - contribution_id: hook1
      hook_key: app.started
    - contribution_id: hook2
      hook_key: app.stopped
"""
        manifest = parse_manifest(yaml_str)

        assert len(manifest.contributions.slots) == 2
        assert len(manifest.contributions.hooks) == 2

    def test_parse_default_priority(self) -> None:
        """Contributions without priority should default to 50."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
contributions:
  slots:
    - contribution_id: c1
      slot_key: ui.sidebar
  hooks:
    - contribution_id: h1
      hook_key: app.started
"""
        manifest = parse_manifest(yaml_str)

        assert manifest.contributions.slots[0].priority == 50
        assert manifest.contributions.hooks[0].priority == 50


class TestParseManifestErrors:
    """Tests for manifest parsing error handling."""

    def test_invalid_yaml_raises(self) -> None:
        """Invalid YAML should raise ManifestError."""
        with pytest.raises(ManifestError, match="Invalid YAML"):
            parse_manifest("{ invalid yaml: [")

    def test_non_mapping_raises(self) -> None:
        """Non-mapping YAML should raise ManifestError."""
        with pytest.raises(ManifestError, match="must be a YAML mapping"):
            parse_manifest("- just\n- a\n- list")

    def test_missing_manifest_version_raises(self) -> None:
        """Missing manifest_version should raise ManifestError."""
        yaml_str = """
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
"""
        with pytest.raises(ManifestError, match="Missing required field: manifest_version"):
            parse_manifest(yaml_str)

    def test_missing_plugin_id_raises(self) -> None:
        """Missing plugin_id should raise ManifestError."""
        yaml_str = """
manifest_version: "1"
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
"""
        with pytest.raises(ManifestError, match="Missing required field: plugin_id"):
            parse_manifest(yaml_str)

    def test_invalid_version_raises(self) -> None:
        """Invalid plugin_version should raise ManifestError."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "not.a.version"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
"""
        with pytest.raises(ManifestError, match="Invalid plugin_version"):
            parse_manifest(yaml_str)

    def test_invalid_requires_switchboard_raises(self) -> None:
        """Invalid requires_switchboard should raise ManifestError."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: "invalid range"
entrypoint: test:Plugin
"""
        with pytest.raises(ManifestError, match="Invalid requires_switchboard"):
            parse_manifest(yaml_str)

    def test_wrong_type_raises(self) -> None:
        """Wrong field type should raise ManifestError."""
        yaml_str = """
manifest_version: 1
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
"""
        with pytest.raises(ManifestError, match="must be str"):
            parse_manifest(yaml_str)

    def test_contributions_not_mapping_raises(self) -> None:
        """contributions must be a mapping."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
contributions: "not a mapping"
"""
        with pytest.raises(ManifestError, match="contributions must be a mapping"):
            parse_manifest(yaml_str)

    def test_slots_not_list_raises(self) -> None:
        """contributions.slots must be a list."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
contributions:
  slots: "not a list"
"""
        with pytest.raises(ManifestError, match=r"contributions\.slots must be a list"):
            parse_manifest(yaml_str)

    def test_slot_missing_contribution_id_raises(self) -> None:
        """Slot contribution must have contribution_id."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
contributions:
  slots:
    - slot_key: ui.sidebar
"""
        with pytest.raises(ManifestError, match="Missing required field: contribution_id"):
            parse_manifest(yaml_str)

    def test_hook_missing_hook_key_raises(self) -> None:
        """Hook contribution must have hook_key."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
contributions:
  hooks:
    - contribution_id: h1
"""
        with pytest.raises(ManifestError, match="Missing required field: hook_key"):
            parse_manifest(yaml_str)


class TestLoadManifest:
    """Tests for load_manifest()."""

    def test_load_from_file(self) -> None:
        """Load a manifest from a file."""
        yaml_content = """
manifest_version: "1"
plugin_id: com.example.file
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: file_plugin:Plugin
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            manifest = load_manifest(f.name)

        assert manifest.plugin_id == "com.example.file"

        # Cleanup
        Path(f.name).unlink()

    def test_load_from_path_object(self) -> None:
        """Load a manifest from a Path object."""
        yaml_content = """
manifest_version: "1"
plugin_id: com.example.path
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: path_plugin:Plugin
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = Path(f.name)

            manifest = load_manifest(path)

        assert manifest.plugin_id == "com.example.path"

        # Cleanup
        path.unlink()

    def test_load_nonexistent_file_raises(self) -> None:
        """Loading a nonexistent file should raise."""
        with pytest.raises(ManifestError, match="Cannot read manifest file"):
            load_manifest("/nonexistent/path/manifest.yaml")


class TestUnknownFieldsIgnored:
    """Test that unknown fields are ignored (forward compatibility)."""

    def test_unknown_top_level_fields_ignored(self) -> None:
        """Unknown top-level fields should be ignored."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
future_field: some value
another_unknown: 123
"""
        manifest = parse_manifest(yaml_str)
        assert manifest.plugin_id == "com.example.test"

    def test_unknown_contribution_fields_ignored(self) -> None:
        """Unknown fields in contributions should be stored in metadata or ignored."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
contributions:
  slots:
    - contribution_id: c1
      slot_key: ui.sidebar
      future_field: ignored
"""
        # Should not raise
        manifest = parse_manifest(yaml_str)
        assert len(manifest.contributions.slots) == 1


class TestDependencyFields:
    """Tests for requires and optional_requires fields (V2)."""

    def test_requires_empty_by_default(self) -> None:
        """Manifest without requires should have empty tuple."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
"""
        manifest = parse_manifest(yaml_str)
        assert manifest.requires == ()
        assert manifest.optional_requires == ()

    def test_requires_parses_list(self) -> None:
        """requires field should parse as list of plugin IDs."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
requires:
  - com.example.core
  - com.example.logging
"""
        manifest = parse_manifest(yaml_str)
        assert manifest.requires == ("com.example.core", "com.example.logging")

    def test_optional_requires_parses_list(self) -> None:
        """optional_requires field should parse as list of plugin IDs."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
optional_requires:
  - com.example.analytics
  - com.example.telemetry
"""
        manifest = parse_manifest(yaml_str)
        assert manifest.optional_requires == ("com.example.analytics", "com.example.telemetry")

    def test_requires_and_optional_together(self) -> None:
        """Both requires and optional_requires can be specified."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
requires:
  - com.example.core
optional_requires:
  - com.example.analytics
"""
        manifest = parse_manifest(yaml_str)
        assert manifest.requires == ("com.example.core",)
        assert manifest.optional_requires == ("com.example.analytics",)

    def test_requires_not_list_raises(self) -> None:
        """requires must be a list."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
requires: "not a list"
"""
        with pytest.raises(ManifestError, match="requires must be a list"):
            parse_manifest(yaml_str)

    def test_requires_item_not_string_raises(self) -> None:
        """requires items must be strings."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
requires:
  - 123
"""
        with pytest.raises(ManifestError, match=r"requires\[0\] must be a string"):
            parse_manifest(yaml_str)

    def test_optional_requires_not_list_raises(self) -> None:
        """optional_requires must be a list."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
optional_requires: "not a list"
"""
        with pytest.raises(ManifestError, match="optional_requires must be a list"):
            parse_manifest(yaml_str)

    def test_empty_requires_list(self) -> None:
        """Empty requires list should parse to empty tuple."""
        yaml_str = """
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0"
entrypoint: test:Plugin
requires: []
"""
        manifest = parse_manifest(yaml_str)
        assert manifest.requires == ()
