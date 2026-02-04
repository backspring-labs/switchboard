"""Export readiness tests - proving Switchboard embeds cleanly.

These tests verify that Switchboard can be safely installed and embedded
in a host application with no surprises.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import switchboard
from switchboard import (
    ActivationPlan,
    ApiRange,
    HookDefinition,
    HookKind,
    HookPolicy,
    PatchPanel,
    PluginManifest,
    RuntimeInfo,
    RuntimeSnapshot,
    SlotDefinition,
    SlotPolicy,
    parse_manifest,
)
from switchboard.adapters.hook_router_memory import MemoryHookRouter
from switchboard.adapters.loader import ImportLoader
from switchboard.domain.models import (
    ManifestContributions,
    SemVer,
)

# =============================================================================
# 4.2 Import Has No Side Effects
# =============================================================================


class TestImportNoSideEffects:
    """Test that importing switchboard has no side effects."""

    def test_import_creates_no_files(self) -> None:
        """Importing switchboard should not create any files in cwd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run import in subprocess with clean cwd
            result = subprocess.run(
                [sys.executable, "-c", "import switchboard"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Import failed: {result.stderr}"

            # Check no files were created
            files = list(Path(tmpdir).iterdir())
            assert files == [], f"Files created during import: {files}"

    def test_import_succeeds(self) -> None:
        """Basic import should succeed."""
        # Re-import should work without issues
        import importlib

        importlib.reload(switchboard)

    def test_no_automatic_plugin_discovery(self) -> None:
        """Importing should not trigger automatic plugin discovery."""
        # Create a fresh panel - it should be empty
        panel = PatchPanel(slots=[], hooks=[])
        assert panel.list_plugins() == []


# =============================================================================
# 4.4 Public API Surface Check
# =============================================================================


class TestPublicApiSurface:
    """Test that the public API is stable and accessible."""

    def test_patchpanel_importable(self) -> None:
        """PatchPanel can be imported from top level."""
        from switchboard import PatchPanel

        assert PatchPanel is not None

    def test_definitions_importable(self) -> None:
        """Definition types can be imported."""
        from switchboard import HookDefinition, SlotDefinition

        assert SlotDefinition is not None
        assert HookDefinition is not None

    def test_policies_importable(self) -> None:
        """Policy enums can be imported."""
        from switchboard import HookKind, SlotPolicy

        assert SlotPolicy.MULTI is not None
        assert SlotPolicy.SINGLE is not None
        assert HookKind.EVENT is not None
        assert HookPolicy.BROADCAST is not None

    def test_manifest_functions_importable(self) -> None:
        """Manifest functions can be imported."""
        from switchboard import load_manifest, parse_manifest

        assert parse_manifest is not None
        assert load_manifest is not None

    def test_errors_importable(self) -> None:
        """Error types can be imported."""
        from switchboard import (
            ManifestError,
            PluginNotFoundError,
            SwitchboardError,
        )

        assert SwitchboardError is not None
        assert ManifestError is not None
        assert PluginNotFoundError is not None

    def test_introspection_types_importable(self) -> None:
        """V2 introspection types can be imported."""
        from switchboard import (
            ActivationPlan,
            RuntimeSnapshot,
        )

        assert RuntimeInfo is not None
        assert RuntimeSnapshot is not None
        assert ActivationPlan is not None

    def test_dunder_all_matches_exports(self) -> None:
        """__all__ should list all intended public exports."""
        import switchboard

        # All items in __all__ should be importable
        for name in switchboard.__all__:
            assert hasattr(switchboard, name), f"{name} in __all__ but not importable"

    def test_version_available(self) -> None:
        """__version__ should be available."""
        import switchboard

        assert hasattr(switchboard, "__version__")
        assert isinstance(switchboard.__version__, str)


# =============================================================================
# 4.5 No Global State / Multi-Panel Isolation
# =============================================================================


class TestMultiPanelIsolation:
    """Test that multiple PatchPanels in-process do not bleed state."""

    def test_two_panels_independent_slots(self) -> None:
        """Two panels have independent slot definitions."""
        panel1 = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
        )
        panel2 = PatchPanel(
            slots=[SlotDefinition("ui.main")],
            hooks=[],
        )

        assert panel1.list_slots() == ["ui.sidebar"]
        assert panel2.list_slots() == ["ui.main"]

    def test_two_panels_independent_hooks(self) -> None:
        """Two panels have independent hook definitions."""
        panel1 = PatchPanel(
            slots=[],
            hooks=[HookDefinition("app.started")],
        )
        panel2 = PatchPanel(
            slots=[],
            hooks=[HookDefinition("app.stopped")],
        )

        assert panel1.list_hooks() == ["app.started"]
        assert panel2.list_hooks() == ["app.stopped"]

    def test_two_panels_independent_plugins(self) -> None:
        """Plugins registered in one panel don't appear in another."""
        panel1 = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            hook_router=MemoryHookRouter(),
            loader=ImportLoader(),
        )
        panel2 = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            hook_router=MemoryHookRouter(),
            loader=ImportLoader(),
        )

        manifest = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.test",
            plugin_version=SemVer(1, 0, 0),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
            contributions=ManifestContributions(),
        )

        panel1.register_manifest(manifest)

        assert panel1.list_plugins() == ["com.example.test"]
        assert panel2.list_plugins() == []

    def test_two_panels_independent_snapshots(self) -> None:
        """Each panel's snapshot reflects only its own state."""
        panel1 = PatchPanel(
            slots=[SlotDefinition("slot.a")],
            hooks=[HookDefinition("hook.a")],
        )
        panel2 = PatchPanel(
            slots=[SlotDefinition("slot.b"), SlotDefinition("slot.c")],
            hooks=[],
        )

        snap1 = panel1.snapshot()
        snap2 = panel2.snapshot()

        assert snap1.runtime.slot_count == 1
        assert snap1.runtime.hook_count == 1
        assert snap2.runtime.slot_count == 2
        assert snap2.runtime.hook_count == 0


# =============================================================================
# 4.6 Host Embedding Smoke Test
# =============================================================================


class TestHostEmbeddingSmoke:
    """Minimal end-to-end test proving the host embedding flow works."""

    def test_full_embedding_flow(self) -> None:
        """Complete host embedding smoke test."""
        # 1. Construct PatchPanel with slots and hooks
        panel = PatchPanel(
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

        # 2. Parse manifest from YAML
        manifest = parse_manifest("""
manifest_version: "1"
plugin_id: com.example.smoke
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: tests.fixtures.sample_plugin:SamplePlugin
contributions:
  slots:
    - contribution_id: sidebar.widget
      slot_key: ui.sidebar
      priority: 50
  hooks:
    - contribution_id: on.started
      hook_key: app.started
      handler: tests.fixtures.sample_plugin:on_app_started
      priority: 50
""")

        # 3. Register and activate plugin
        panel.register_manifest(manifest)
        panel.activate("com.example.smoke")

        # 4. Resolve slot - verify contributions
        contributions = panel.resolve_slot("ui.sidebar")
        assert len(contributions) == 1
        assert contributions[0].contribution_id == "sidebar.widget"
        assert contributions[0].plugin_id == "com.example.smoke"

        # 5. Emit hook - verify handler called
        results = panel.emit("app.started", {"timestamp": 12345})
        assert len(results) == 1
        assert "started:12345" in results[0]

        # 6. Snapshot - verify state
        snap = panel.snapshot()
        assert isinstance(snap, RuntimeSnapshot)
        assert snap.runtime.plugin_count == 1
        assert snap.runtime.active_plugin_count == 1
        assert len(snap.plugins) == 1
        assert snap.plugins[0].state == "active"

    def test_activation_plan_flow(self) -> None:
        """Test activation planning with dependencies."""
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            hook_router=MemoryHookRouter(),
            loader=ImportLoader(),
        )

        # Register plugins with dependencies
        core_manifest = parse_manifest("""
manifest_version: "1"
plugin_id: com.example.core
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: tests.fixtures.sample_plugin:SamplePlugin
""")

        feature_manifest = parse_manifest("""
manifest_version: "1"
plugin_id: com.example.feature
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: tests.fixtures.sample_plugin:AnotherPlugin
requires:
  - com.example.core
""")

        panel.register_manifest(core_manifest)
        panel.register_manifest(feature_manifest)

        # Get activation plan
        plan = panel.activation_plan()
        assert isinstance(plan, ActivationPlan)
        assert plan.order.index("com.example.core") < plan.order.index("com.example.feature")

        # Activate all
        result = panel.activate_all()
        assert "com.example.core" in result.order
        assert "com.example.feature" in result.order
        assert result.blocked == {}

        # Verify states
        assert panel.get_plugin_state("com.example.core").value == "active"
        assert panel.get_plugin_state("com.example.feature").value == "active"

    def test_dump_state_readable(self) -> None:
        """dump_state produces readable output."""
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[HookDefinition("app.started")],
            hook_router=MemoryHookRouter(),
            loader=ImportLoader(),
        )

        manifest = parse_manifest("""
manifest_version: "1"
plugin_id: com.example.test
plugin_version: "1.0.0"
requires_switchboard: ">=0.1.0,<1.0.0"
entrypoint: tests.fixtures.sample_plugin:SamplePlugin
""")
        panel.register_manifest(manifest)
        panel.activate("com.example.test")

        # Text format
        text = panel.dump_state(format="text")
        assert "Switchboard Runtime State" in text
        assert "com.example.test" in text
        assert "[active]" in text

        # JSON format
        import json

        json_str = panel.dump_state(format="json")
        data = json.loads(json_str)
        assert "plugins" in data
        assert len(data["plugins"]) == 1
