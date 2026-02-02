"""Golden path tests parameterized to run with both MemoryHookRouter and PluggyHookRouter.

This ensures both router implementations behave identically.
"""

import pytest

from switchboard import (
    ApiRange,
    HookContribution,
    HookDefinition,
    HookKind,
    ManifestContributions,
    PatchPanel,
    PluginManifest,
    SemVer,
    SlotContribution,
    SlotDefinition,
    SlotPolicy,
)
from switchboard.adapters.hook_router_memory import MemoryHookRouter
from switchboard.adapters.hook_router_pluggy import PluggyHookRouter
from switchboard.adapters.loader import ImportLoader


def make_manifest(
    plugin_id: str,
    slots: tuple[SlotContribution, ...] = (),
    hooks: tuple[HookContribution, ...] = (),
) -> PluginManifest:
    """Create a test manifest."""
    return PluginManifest(
        manifest_version="1",
        plugin_id=plugin_id,
        plugin_version=SemVer.parse("1.0.0"),
        requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
        entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
        contributions=ManifestContributions(slots=slots, hooks=hooks),
    )


@pytest.fixture(params=["memory", "pluggy"])
def router(request: pytest.FixtureRequest):
    """Parameterized fixture that provides both router implementations."""
    if request.param == "memory":
        return MemoryHookRouter()
    else:
        return PluggyHookRouter()


class TestGoldenPathBothRouters:
    """Golden path tests that run with both router implementations."""

    def test_complete_flow(self, router) -> None:
        """Test the complete flow with both routers."""
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[
                SlotDefinition("ui.sidebar", policy=SlotPolicy.MULTI),
            ],
            hooks=[
                HookDefinition("app.started", kind=HookKind.LIFECYCLE),
            ],
            hook_router=router,
            loader=loader,
        )

        # Register and activate plugin
        slot_contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="sidebar.widget",
            slot_key="ui.sidebar",
            priority=50,
        )
        hook_contrib = HookContribution(
            plugin_id="com.example.test",
            contribution_id="on.started",
            hook_key="app.started",
            priority=50,
            handler="tests.fixtures.sample_plugin:on_app_started",
        )
        manifest = make_manifest(
            "com.example.test",
            slots=(slot_contrib,),
            hooks=(hook_contrib,),
        )
        panel.register_manifest(manifest)
        panel.activate("com.example.test")

        # Verify slot resolution
        sidebar_items = panel.resolve_slot("ui.sidebar")
        assert len(sidebar_items) == 1
        assert sidebar_items[0].plugin_id == "com.example.test"

        # Verify hook emission
        results = panel.emit("app.started", payload={"timestamp": 12345})
        assert results == ["started:12345"]

    def test_priority_ordering(self, router) -> None:
        """Test that priority ordering works with both routers."""
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("app.started", kind=HookKind.LIFECYCLE)],
            hook_router=router,
            loader=loader,
        )

        # Register two plugins with different priorities
        for plugin_id, priority, handler in [
            ("com.low", 10, "tests.fixtures.sample_plugin:on_app_started"),
            ("com.high", 100, "tests.fixtures.sample_plugin:on_app_started_high_priority"),
        ]:
            hook = HookContribution(
                plugin_id=plugin_id,
                contribution_id="handler",
                hook_key="app.started",
                priority=priority,
                handler=handler,
            )
            manifest = PluginManifest(
                manifest_version="1",
                plugin_id=plugin_id,
                plugin_version=SemVer.parse("1.0.0"),
                requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
                entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
                contributions=ManifestContributions(hooks=(hook,)),
            )
            panel.register_manifest(manifest)
            panel.activate(plugin_id)

        # Higher priority should be first
        results = panel.emit("app.started", payload={"timestamp": 999})
        assert results == ["high:999", "started:999"]

    def test_first_result_policy(self, router) -> None:
        """Test first_result policy with both routers."""
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("command.run", kind=HookKind.COMMAND)],
            hook_router=router,
            loader=loader,
        )

        # Register command handler
        hook = HookContribution(
            plugin_id="com.example.cmd",
            contribution_id="cmd",
            hook_key="command.run",
            priority=100,
            handler="tests.fixtures.sample_plugin:command_handler",
        )
        manifest = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.cmd",
            plugin_version=SemVer.parse("1.0.0"),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
            contributions=ManifestContributions(hooks=(hook,)),
        )
        panel.register_manifest(manifest)
        panel.activate("com.example.cmd")

        # Test matching command
        result = panel.emit("command.run", payload={"command": "greet", "name": "Bob"})
        assert result == {"greeting": "Hello, Bob!"}

        # Test non-matching command (returns None)
        result = panel.emit("command.run", payload={"command": "unknown"})
        assert result is None

    def test_deactivation_removes_handlers(self, router) -> None:
        """Test that deactivation removes handlers with both routers."""
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("app.started")],
            hook_router=router,
            loader=loader,
        )

        hook = HookContribution(
            plugin_id="com.example.test",
            contribution_id="handler",
            hook_key="app.started",
            handler="tests.fixtures.sample_plugin:on_app_started",
        )
        manifest = make_manifest("com.example.test", hooks=(hook,))
        panel.register_manifest(manifest)
        panel.activate("com.example.test")

        # Handler is active
        results = panel.emit("app.started", payload={"timestamp": 1})
        assert len(results) == 1

        # Deactivate
        panel.deactivate("com.example.test")

        # Handler is removed
        results = panel.emit("app.started", payload={"timestamp": 1})
        assert len(results) == 0
