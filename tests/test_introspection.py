"""Tests for V2 introspection features."""

from __future__ import annotations

import sys
from datetime import UTC

import pytest

from switchboard import (
    ContributionSnapshot,
    HookContribution,
    HookDefinition,
    HookKind,
    PatchPanel,
    PluginManifest,
    PluginSnapshot,
    RuntimeInfo,
    RuntimeSnapshot,
    SlotContribution,
    SlotDefinition,
    SlotPolicy,
)
from switchboard.adapters.hook_router_memory import MemoryHookRouter
from switchboard.adapters.loader import ImportLoader
from switchboard.domain.models import ApiRange, ManifestContributions, SemVer

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def panel() -> PatchPanel:
    """Create a PatchPanel with some slots and hooks."""
    return PatchPanel(
        slots=[
            SlotDefinition("ui.sidebar", policy=SlotPolicy.MULTI),
            SlotDefinition("ui.main", policy=SlotPolicy.SINGLE),
        ],
        hooks=[
            HookDefinition("app.started", kind=HookKind.LIFECYCLE),
            HookDefinition("command.run", kind=HookKind.COMMAND),
        ],
        hook_router=MemoryHookRouter(),
        loader=ImportLoader(),
    )


@pytest.fixture
def sample_manifest() -> PluginManifest:
    """Create a sample plugin manifest."""
    return PluginManifest(
        manifest_version="1",
        plugin_id="com.example.test",
        plugin_version=SemVer(1, 0, 0),
        requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
        entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
        contributions=ManifestContributions(),
    )


@pytest.fixture
def manifest_with_contributions() -> PluginManifest:
    """Create a manifest with slot and hook contributions."""
    return PluginManifest(
        manifest_version="1",
        plugin_id="com.example.contrib",
        plugin_version=SemVer(2, 0, 0),
        requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
        entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
        contributions=ManifestContributions(
            slots=(
                SlotContribution(
                    plugin_id="com.example.contrib",
                    contribution_id="sidebar.widget",
                    slot_key="ui.sidebar",
                    priority=75,
                ),
            ),
            hooks=(
                HookContribution(
                    plugin_id="com.example.contrib",
                    contribution_id="on.started",
                    hook_key="app.started",
                    handler="tests.fixtures.sample_plugin:on_app_started",
                    priority=60,
                ),
            ),
        ),
    )


# =============================================================================
# runtime_info() Tests
# =============================================================================


class TestRuntimeInfo:
    """Tests for PatchPanel.runtime_info()."""

    def test_runtime_info_returns_runtime_info_type(self, panel: PatchPanel) -> None:
        """runtime_info() returns a RuntimeInfo instance."""
        info = panel.runtime_info()
        assert isinstance(info, RuntimeInfo)

    def test_runtime_info_framework_version_is_string(self, panel: PatchPanel) -> None:
        """Framework version is a non-empty string."""
        info = panel.runtime_info()
        assert isinstance(info.framework_version, str)
        assert len(info.framework_version) > 0

    def test_runtime_info_python_version_matches_sys(self, panel: PatchPanel) -> None:
        """Python version matches sys.version_info."""
        info = panel.runtime_info()
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert info.python_version == expected

    def test_runtime_info_slot_count(self, panel: PatchPanel) -> None:
        """Slot count matches defined slots."""
        info = panel.runtime_info()
        assert info.slot_count == 2

    def test_runtime_info_hook_count(self, panel: PatchPanel) -> None:
        """Hook count matches defined hooks."""
        info = panel.runtime_info()
        assert info.hook_count == 2

    def test_runtime_info_plugin_count_empty(self, panel: PatchPanel) -> None:
        """Plugin count is zero with no registered plugins."""
        info = panel.runtime_info()
        assert info.plugin_count == 0
        assert info.active_plugin_count == 0

    def test_runtime_info_plugin_count_after_register(
        self, panel: PatchPanel, sample_manifest: PluginManifest
    ) -> None:
        """Plugin count increments after registration."""
        panel.register_manifest(sample_manifest)
        info = panel.runtime_info()
        assert info.plugin_count == 1
        assert info.active_plugin_count == 0  # Not activated yet

    def test_runtime_info_active_count_after_activate(
        self, panel: PatchPanel, sample_manifest: PluginManifest
    ) -> None:
        """Active plugin count increments after activation."""
        panel.register_manifest(sample_manifest)
        panel.activate("com.example.test")
        info = panel.runtime_info()
        assert info.plugin_count == 1
        assert info.active_plugin_count == 1

    def test_runtime_info_is_frozen(self, panel: PatchPanel) -> None:
        """RuntimeInfo is immutable (frozen dataclass)."""
        info = panel.runtime_info()
        with pytest.raises(AttributeError):
            info.plugin_count = 999  # type: ignore[misc]

    def test_runtime_info_never_throws(self) -> None:
        """runtime_info() never throws, even with minimal panel."""
        panel = PatchPanel(slots=[], hooks=[])
        info = panel.runtime_info()
        assert info.slot_count == 0
        assert info.hook_count == 0
        assert info.plugin_count == 0


# =============================================================================
# snapshot() Tests
# =============================================================================


class TestSnapshot:
    """Tests for PatchPanel.snapshot()."""

    def test_snapshot_returns_runtime_snapshot_type(self, panel: PatchPanel) -> None:
        """snapshot() returns a RuntimeSnapshot instance."""
        snap = panel.snapshot()
        assert isinstance(snap, RuntimeSnapshot)

    def test_snapshot_has_utc_timestamp(self, panel: PatchPanel) -> None:
        """Snapshot timestamp is timezone-aware (UTC)."""
        snap = panel.snapshot()
        assert snap.timestamp.tzinfo is not None
        assert snap.timestamp.tzinfo == UTC

    def test_snapshot_includes_runtime_info(self, panel: PatchPanel) -> None:
        """Snapshot includes RuntimeInfo."""
        snap = panel.snapshot()
        assert isinstance(snap.runtime, RuntimeInfo)
        assert snap.runtime.slot_count == 2
        assert snap.runtime.hook_count == 2

    def test_snapshot_empty_plugins(self, panel: PatchPanel) -> None:
        """Snapshot shows empty plugins list when none registered."""
        snap = panel.snapshot()
        assert snap.plugins == ()

    def test_snapshot_shows_registered_plugin(
        self, panel: PatchPanel, sample_manifest: PluginManifest
    ) -> None:
        """Snapshot shows registered plugins."""
        panel.register_manifest(sample_manifest)
        snap = panel.snapshot()

        assert len(snap.plugins) == 1
        plugin = snap.plugins[0]
        assert isinstance(plugin, PluginSnapshot)
        assert plugin.plugin_id == "com.example.test"
        assert plugin.version == "1.0.0"
        assert plugin.state == "ready"

    def test_snapshot_shows_active_plugin_state(
        self, panel: PatchPanel, sample_manifest: PluginManifest
    ) -> None:
        """Snapshot shows active state after activation."""
        panel.register_manifest(sample_manifest)
        panel.activate("com.example.test")
        snap = panel.snapshot()

        assert snap.plugins[0].state == "active"

    def test_snapshot_shows_slots(self, panel: PatchPanel) -> None:
        """Snapshot shows all defined slots."""
        snap = panel.snapshot()

        assert len(snap.slots) == 2
        slot_keys = {s.slot_key for s in snap.slots}
        assert slot_keys == {"ui.sidebar", "ui.main"}

    def test_snapshot_slot_shows_policy(self, panel: PatchPanel) -> None:
        """Slot snapshot includes policy."""
        snap = panel.snapshot()

        sidebar = next(s for s in snap.slots if s.slot_key == "ui.sidebar")
        assert sidebar.policy == "multi"

        main = next(s for s in snap.slots if s.slot_key == "ui.main")
        assert main.policy == "single"

    def test_snapshot_shows_hooks(self, panel: PatchPanel) -> None:
        """Snapshot shows all defined hooks."""
        snap = panel.snapshot()

        assert len(snap.hooks) == 2
        hook_keys = {h.hook_key for h in snap.hooks}
        assert hook_keys == {"app.started", "command.run"}

    def test_snapshot_hook_shows_kind_and_policy(self, panel: PatchPanel) -> None:
        """Hook snapshot includes kind and effective policy."""
        snap = panel.snapshot()

        started = next(h for h in snap.hooks if h.hook_key == "app.started")
        assert started.kind == "lifecycle"
        assert started.policy == "broadcast"

        command = next(h for h in snap.hooks if h.hook_key == "command.run")
        assert command.kind == "command"
        assert command.policy == "first_result"

    def test_snapshot_shows_slot_contributions(
        self, panel: PatchPanel, manifest_with_contributions: PluginManifest
    ) -> None:
        """Snapshot shows slot contributions from active plugins."""
        panel.register_manifest(manifest_with_contributions)
        panel.activate("com.example.contrib")
        snap = panel.snapshot()

        sidebar = next(s for s in snap.slots if s.slot_key == "ui.sidebar")
        assert len(sidebar.contributions) == 1

        contrib = sidebar.contributions[0]
        assert isinstance(contrib, ContributionSnapshot)
        assert contrib.contribution_id == "sidebar.widget"
        assert contrib.plugin_id == "com.example.contrib"
        assert contrib.priority == 75

    def test_snapshot_shows_hook_handlers(
        self, panel: PatchPanel, manifest_with_contributions: PluginManifest
    ) -> None:
        """Snapshot shows hook handlers from active plugins."""
        panel.register_manifest(manifest_with_contributions)
        panel.activate("com.example.contrib")
        snap = panel.snapshot()

        started = next(h for h in snap.hooks if h.hook_key == "app.started")
        assert len(started.handlers) == 1

        handler = started.handlers[0]
        assert isinstance(handler, ContributionSnapshot)
        assert handler.contribution_id == "on.started"
        assert handler.plugin_id == "com.example.contrib"
        assert handler.priority == 60

    def test_snapshot_excludes_inactive_plugin_contributions(
        self, panel: PatchPanel, manifest_with_contributions: PluginManifest
    ) -> None:
        """Snapshot only shows contributions from active plugins."""
        panel.register_manifest(manifest_with_contributions)
        # Plugin registered but not activated
        snap = panel.snapshot()

        sidebar = next(s for s in snap.slots if s.slot_key == "ui.sidebar")
        assert len(sidebar.contributions) == 0

        started = next(h for h in snap.hooks if h.hook_key == "app.started")
        assert len(started.handlers) == 0

    def test_snapshot_plugin_shows_contribution_ids(
        self, panel: PatchPanel, manifest_with_contributions: PluginManifest
    ) -> None:
        """Plugin snapshot lists its contribution IDs."""
        panel.register_manifest(manifest_with_contributions)
        snap = panel.snapshot()

        plugin = snap.plugins[0]
        assert "sidebar.widget" in plugin.contributions
        assert "on.started" in plugin.contributions

    def test_snapshot_is_frozen(self, panel: PatchPanel) -> None:
        """RuntimeSnapshot is immutable (frozen dataclass)."""
        snap = panel.snapshot()
        with pytest.raises(AttributeError):
            snap.plugins = ()  # type: ignore[misc]

    def test_snapshot_deterministic_ordering(self, panel: PatchPanel) -> None:
        """Snapshot ordering is deterministic (sorted keys)."""
        snap1 = panel.snapshot()
        snap2 = panel.snapshot()

        # Slot and hook keys should be in same order
        assert [s.slot_key for s in snap1.slots] == [s.slot_key for s in snap2.slots]
        assert [h.hook_key for h in snap1.hooks] == [h.hook_key for h in snap2.hooks]


# =============================================================================
# dump_state() Tests
# =============================================================================


class TestDumpState:
    """Tests for PatchPanel.dump_state()."""

    def test_dump_state_returns_string(self, panel: PatchPanel) -> None:
        """dump_state() returns a string."""
        result = panel.dump_state()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_dump_state_default_is_text(self, panel: PatchPanel) -> None:
        """Default format is text."""
        text = panel.dump_state()
        assert "=== Switchboard Runtime State ===" in text

    def test_dump_state_text_format(self, panel: PatchPanel) -> None:
        """Text format is human-readable."""
        text = panel.dump_state(format="text")
        assert "Timestamp:" in text
        assert "Runtime:" in text
        assert "Plugins:" in text
        assert "Slots:" in text
        assert "Hooks:" in text

    def test_dump_state_json_format(self, panel: PatchPanel) -> None:
        """JSON format is valid JSON."""
        import json

        result = panel.dump_state(format="json")
        data = json.loads(result)  # Should not raise

        assert "timestamp" in data
        assert "runtime" in data
        assert "plugins" in data
        assert "slots" in data
        assert "hooks" in data

    def test_dump_state_json_has_runtime_info(self, panel: PatchPanel) -> None:
        """JSON contains runtime info fields."""
        import json

        result = panel.dump_state(format="json")
        data = json.loads(result)

        assert "framework_version" in data["runtime"]
        assert "python_version" in data["runtime"]
        assert data["runtime"]["slot_count"] == 2
        assert data["runtime"]["hook_count"] == 2

    def test_dump_state_json_timestamp_is_iso(self, panel: PatchPanel) -> None:
        """JSON timestamp is ISO 8601 format."""
        import json
        from datetime import datetime

        result = panel.dump_state(format="json")
        data = json.loads(result)

        # Should parse without error
        parsed = datetime.fromisoformat(data["timestamp"])
        assert parsed.tzinfo is not None  # Should be timezone-aware

    def test_dump_state_text_shows_plugins(
        self, panel: PatchPanel, sample_manifest: PluginManifest
    ) -> None:
        """Text format shows registered plugins."""
        panel.register_manifest(sample_manifest)
        text = panel.dump_state()

        assert "com.example.test" in text
        assert "[ready]" in text

    def test_dump_state_text_shows_active_state(
        self, panel: PatchPanel, sample_manifest: PluginManifest
    ) -> None:
        """Text format shows active state after activation."""
        panel.register_manifest(sample_manifest)
        panel.activate("com.example.test")
        text = panel.dump_state()

        assert "[active]" in text

    def test_dump_state_json_shows_contributions(
        self, panel: PatchPanel, manifest_with_contributions: PluginManifest
    ) -> None:
        """JSON shows contributions from active plugins."""
        import json

        panel.register_manifest(manifest_with_contributions)
        panel.activate("com.example.contrib")
        result = panel.dump_state(format="json")
        data = json.loads(result)

        # Find sidebar slot
        sidebar = next(s for s in data["slots"] if s["slot_key"] == "ui.sidebar")
        assert len(sidebar["contributions"]) == 1
        assert sidebar["contributions"][0]["contribution_id"] == "sidebar.widget"

    def test_dump_state_deterministic(self, panel: PatchPanel) -> None:
        """Output is deterministic for diffs."""
        text1 = panel.dump_state()
        text2 = panel.dump_state()

        # Content should be identical (except timestamp)
        # Split by lines and compare non-timestamp lines
        lines1 = [line for line in text1.split("\n") if not line.startswith("Timestamp:")]
        lines2 = [line for line in text2.split("\n") if not line.startswith("Timestamp:")]
        assert lines1 == lines2

    def test_dump_state_json_sorted_keys(self, panel: PatchPanel) -> None:
        """JSON has sorted keys for deterministic output."""
        import json

        result = panel.dump_state(format="json")
        data = json.loads(result)

        # Re-serialize with sorted keys and compare
        reserialized = json.dumps(data, indent=2, sort_keys=True)
        assert result == reserialized
