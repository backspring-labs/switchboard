"""Tests for PatchPanel - the central registry and resolver."""

import pytest

from switchboard import (
    ApiRange,
    CompatibilityError,
    DuplicateRegistrationError,
    HookContribution,
    HookDefinition,
    HookNotFoundError,
    LifecycleError,
    ManifestContributions,
    PatchPanel,
    PluginManifest,
    PluginNotFoundError,
    SemVer,
    SlotContribution,
    SlotDefinition,
    SlotNotFoundError,
    SlotPolicy,
)
from switchboard.domain.lifecycle import PluginState


def make_manifest(
    plugin_id: str = "com.example.test",
    version: str = "1.0.0",
    requires: str = ">=0.1.0,<1.0.0",
    slots: tuple[SlotContribution, ...] = (),
    hooks: tuple[HookContribution, ...] = (),
) -> PluginManifest:
    """Helper to create test manifests."""
    return PluginManifest(
        manifest_version="1",
        plugin_id=plugin_id,
        plugin_version=SemVer.parse(version),
        requires_switchboard=ApiRange.parse(requires),
        entrypoint=f"{plugin_id}:Plugin",
        contributions=ManifestContributions(slots=slots, hooks=hooks),
    )


class TestPatchPanelCreation:
    """Tests for PatchPanel initialization."""

    def test_create_empty_panel(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        assert panel.list_plugins() == []
        assert panel.list_slots() == []
        assert panel.list_hooks() == []

    def test_create_with_slots_and_hooks(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar"), SlotDefinition("ui.main")],
            hooks=[HookDefinition("app.started"), HookDefinition("app.stopped")],
        )
        assert set(panel.list_slots()) == {"ui.sidebar", "ui.main"}
        assert set(panel.list_hooks()) == {"app.started", "app.stopped"}

    def test_duplicate_slot_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Duplicate slot key"):
            PatchPanel(
                slots=[SlotDefinition("ui.sidebar"), SlotDefinition("ui.sidebar")],
                hooks=[],
            )

    def test_duplicate_hook_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Duplicate hook key"):
            PatchPanel(
                slots=[],
                hooks=[HookDefinition("app.started"), HookDefinition("app.started")],
            )


class TestPluginRegistration:
    """Tests for manifest registration."""

    def test_register_manifest(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        manifest = make_manifest()

        panel.register_manifest(manifest)

        assert "com.example.test" in panel.list_plugins()
        assert panel.get_plugin_state("com.example.test") == PluginState.READY

    def test_register_duplicate_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        manifest = make_manifest()

        panel.register_manifest(manifest)

        with pytest.raises(DuplicateRegistrationError) as exc_info:
            panel.register_manifest(manifest)

        assert exc_info.value.plugin_id == "com.example.test"

    def test_register_incompatible_version_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        # Current version is 0.1.0, require >= 2.0.0
        manifest = make_manifest(requires=">=2.0.0")

        with pytest.raises(CompatibilityError) as exc_info:
            panel.register_manifest(manifest)

        assert exc_info.value.plugin_id == "com.example.test"
        assert ">=2.0.0" in exc_info.value.required

    def test_register_with_unknown_slot_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="c1",
            slot_key="ui.nonexistent",
        )
        manifest = make_manifest(slots=(contrib,))

        with pytest.raises(SlotNotFoundError) as exc_info:
            panel.register_manifest(manifest)

        assert exc_info.value.slot_key == "ui.nonexistent"

    def test_register_with_unknown_hook_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        contrib = HookContribution(
            plugin_id="com.example.test",
            contribution_id="h1",
            hook_key="event.nonexistent",
        )
        manifest = make_manifest(hooks=(contrib,))

        with pytest.raises(HookNotFoundError) as exc_info:
            panel.register_manifest(manifest)

        assert exc_info.value.hook_key == "event.nonexistent"

    def test_unregister_plugin(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        manifest = make_manifest()
        panel.register_manifest(manifest)

        panel.unregister("com.example.test")

        assert "com.example.test" not in panel.list_plugins()

    def test_unregister_unknown_plugin_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])

        with pytest.raises(PluginNotFoundError):
            panel.unregister("nonexistent")


class TestSlotResolution:
    """Tests for resolve_slot()."""

    def test_resolve_empty_slot(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
        )

        result = panel.resolve_slot("ui.sidebar")
        assert result == []

    def test_resolve_unknown_slot_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])

        with pytest.raises(SlotNotFoundError):
            panel.resolve_slot("nonexistent")

    def test_resolve_only_returns_active_contributions(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
        )
        contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="c1",
            slot_key="ui.sidebar",
        )
        manifest = make_manifest(slots=(contrib,))
        panel.register_manifest(manifest)

        # Plugin is in READY state, not ACTIVE
        result = panel.resolve_slot("ui.sidebar")
        assert result == []

    def test_resolve_ordering_by_priority(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            loader=FakeLoader(),
        )

        # Register plugin A with priority 10
        contrib_a = SlotContribution(
            plugin_id="com.example.a",
            contribution_id="c1",
            slot_key="ui.sidebar",
            priority=10,
        )
        panel.register_manifest(make_manifest(plugin_id="com.example.a", slots=(contrib_a,)))
        panel.activate("com.example.a")

        # Register plugin B with priority 100
        contrib_b = SlotContribution(
            plugin_id="com.example.b",
            contribution_id="c1",
            slot_key="ui.sidebar",
            priority=100,
        )
        panel.register_manifest(make_manifest(plugin_id="com.example.b", slots=(contrib_b,)))
        panel.activate("com.example.b")

        result = panel.resolve_slot("ui.sidebar")

        # Higher priority first
        assert len(result) == 2
        assert result[0].plugin_id == "com.example.b"
        assert result[1].plugin_id == "com.example.a"

    def test_resolve_ordering_tiebreak_by_plugin_id(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            loader=FakeLoader(),
        )

        # Both have same priority
        for plugin_id in ["com.example.z", "com.example.a"]:
            contrib = SlotContribution(
                plugin_id=plugin_id,
                contribution_id="c1",
                slot_key="ui.sidebar",
                priority=50,
            )
            panel.register_manifest(make_manifest(plugin_id=plugin_id, slots=(contrib,)))
            panel.activate(plugin_id)

        result = panel.resolve_slot("ui.sidebar")

        # Alphabetical by plugin_id for tie-break
        assert result[0].plugin_id == "com.example.a"
        assert result[1].plugin_id == "com.example.z"

    def test_resolve_single_policy_returns_one(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.main", policy=SlotPolicy.SINGLE)],
            hooks=[],
            loader=FakeLoader(),
        )

        for plugin_id, priority in [("com.a", 10), ("com.b", 100), ("com.c", 50)]:
            contrib = SlotContribution(
                plugin_id=plugin_id,
                contribution_id="c1",
                slot_key="ui.main",
                priority=priority,
            )
            panel.register_manifest(make_manifest(plugin_id=plugin_id, slots=(contrib,)))
            panel.activate(plugin_id)

        result = panel.resolve_slot("ui.main")

        # Only highest priority
        assert len(result) == 1
        assert result[0].plugin_id == "com.b"


class TestPluginActivation:
    """Tests for activate() and deactivate()."""

    def test_activate_requires_loader(self) -> None:
        panel = PatchPanel(slots=[], hooks=[])
        panel.register_manifest(make_manifest())

        with pytest.raises(RuntimeError, match="No loader configured"):
            panel.activate("com.example.test")

    def test_activate_unknown_plugin_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], loader=FakeLoader())

        with pytest.raises(PluginNotFoundError):
            panel.activate("nonexistent")

    def test_activate_success(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], loader=FakeLoader())
        panel.register_manifest(make_manifest())

        panel.activate("com.example.test")

        assert panel.get_plugin_state("com.example.test") == PluginState.ACTIVE

    def test_activate_twice_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], loader=FakeLoader())
        panel.register_manifest(make_manifest())
        panel.activate("com.example.test")

        with pytest.raises(LifecycleError):
            panel.activate("com.example.test")

    def test_deactivate_success(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], loader=FakeLoader())
        panel.register_manifest(make_manifest())
        panel.activate("com.example.test")

        panel.deactivate("com.example.test")

        assert panel.get_plugin_state("com.example.test") == PluginState.READY

    def test_deactivate_not_active_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], loader=FakeLoader())
        panel.register_manifest(make_manifest())

        with pytest.raises(LifecycleError):
            panel.deactivate("com.example.test")

    def test_unregister_active_plugin_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], loader=FakeLoader())
        panel.register_manifest(make_manifest())
        panel.activate("com.example.test")

        with pytest.raises(LifecycleError):
            panel.unregister("com.example.test")

    def test_deactivation_removes_contributions(self) -> None:
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            loader=FakeLoader(),
        )
        contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="c1",
            slot_key="ui.sidebar",
        )
        panel.register_manifest(make_manifest(slots=(contrib,)))
        panel.activate("com.example.test")

        assert len(panel.resolve_slot("ui.sidebar")) == 1

        panel.deactivate("com.example.test")

        assert len(panel.resolve_slot("ui.sidebar")) == 0

    def test_activation_rollback_cleans_up_partial_registrations(self) -> None:
        """Test that rollback removes slot contributions if hook handler loading fails."""

        class FailingLoader:
            """Loader that fails when loading hook handlers."""

            def load_entrypoint(self, entrypoint: str) -> FakePlugin:
                return FakePlugin()

            def load_callable(self, import_path: str) -> object:
                raise ImportError(f"Cannot load {import_path}")

        class TrackingRouter:
            """Router that tracks registrations."""

            def __init__(self) -> None:
                self.registered: list[str] = []
                self.unregistered: list[str] = []

            def register_handler(
                self, hook_key: str, contribution: HookContribution, handler: object
            ) -> None:
                self.registered.append(contribution.contribution_id)

            def unregister_handler(self, hook_key: str, contribution_id: str) -> None:
                self.unregistered.append(contribution_id)

        router = TrackingRouter()
        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[HookDefinition("app.started")],
            hook_router=router,
            loader=FailingLoader(),
        )

        slot_contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="slot1",
            slot_key="ui.sidebar",
        )
        hook_contrib = HookContribution(
            plugin_id="com.example.test",
            contribution_id="hook1",
            hook_key="app.started",
            handler="some.module:handler",
        )
        manifest = make_manifest(slots=(slot_contrib,), hooks=(hook_contrib,))
        panel.register_manifest(manifest)

        # Activation should fail when loading the hook handler
        with pytest.raises(ImportError):
            panel.activate("com.example.test")

        # Plugin should be back in READY state (rollback)
        assert panel.get_plugin_state("com.example.test") == PluginState.READY

        # Slot contributions should be cleaned up
        assert len(panel.resolve_slot("ui.sidebar")) == 0

        # Hook handler unregistration should have been called
        assert "hook1" in router.unregistered


class TestHookEmission:
    """Tests for emit()."""

    def test_emit_requires_router(self) -> None:
        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("app.started")],
        )

        with pytest.raises(RuntimeError, match="No hook router configured"):
            panel.emit("app.started", payload={})

    def test_emit_unknown_hook_raises(self) -> None:
        panel = PatchPanel(slots=[], hooks=[], hook_router=FakeRouter())

        with pytest.raises(HookNotFoundError):
            panel.emit("nonexistent", payload={})


# =============================================================================
# Test Helpers (Fake Adapters)
# =============================================================================


class FakePlugin:
    """Fake plugin instance for testing."""

    def __init__(self) -> None:
        self.activated = False
        self.deactivated = False

    def activate(self, context: dict) -> None:
        self.activated = True

    def deactivate(self, context: dict) -> None:
        self.deactivated = True


class FakeLoader:
    """Fake loader for testing."""

    def load_entrypoint(self, entrypoint: str) -> FakePlugin:
        return FakePlugin()

    def load_callable(self, import_path: str) -> object:
        return lambda payload, context: None


class FakeRouter:
    """Fake hook router for testing."""

    def __init__(self) -> None:
        self.handlers: dict[str, list] = {}

    def register_handler(self, hook_key: str, contribution: object, handler: object) -> None:
        if hook_key not in self.handlers:
            self.handlers[hook_key] = []
        self.handlers[hook_key].append(handler)

    def unregister_handler(self, hook_key: str, contribution_id: str) -> None:
        pass

    def emit(
        self,
        hook_key: str,
        policy: object,
        payload: dict,
        context: dict | None = None,
    ) -> list:
        return []

    def clear(self) -> None:
        self.handlers.clear()
