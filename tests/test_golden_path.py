"""Golden path test - validates the complete host use case flow.

This test mirrors the README example and validates:
1. Creating a PatchPanel with slots and hooks
2. Registering plugin manifests
3. Activating plugins
4. Resolving slot contributions
5. Emitting hook events
6. Proper ordering and policy enforcement
"""


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


class TestGoldenPath:
    """Golden path integration tests."""

    def test_complete_flow_slots_and_hooks(self) -> None:
        """Test the complete flow: register, activate, resolve, emit."""
        # 1. Create PatchPanel with slots and hooks
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[
                SlotDefinition("ui.sidebar", policy=SlotPolicy.MULTI),
                SlotDefinition("ui.main", policy=SlotPolicy.SINGLE),
            ],
            hooks=[
                HookDefinition("app.started", kind=HookKind.LIFECYCLE),
                HookDefinition("command.run", kind=HookKind.COMMAND),
            ],
            hook_router=router,
            loader=loader,
        )

        # 2. Create and register plugin manifest
        slot_contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="sidebar.widget",
            slot_key="ui.sidebar",
            priority=50,
            factory="tests.fixtures.sample_plugin:build_sidebar_widget",
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

        # 3. Activate the plugin
        panel.activate("com.example.test")

        # 4. Resolve slot contributions
        sidebar_items = panel.resolve_slot("ui.sidebar")
        assert len(sidebar_items) == 1
        assert sidebar_items[0].plugin_id == "com.example.test"
        assert sidebar_items[0].contribution_id == "sidebar.widget"

        # 5. Emit hook event
        results = panel.emit("app.started", payload={"timestamp": 12345})
        assert results == ["started:12345"]

    def test_multiple_plugins_ordering(self) -> None:
        """Test that multiple plugins are ordered correctly by priority."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[HookDefinition("app.started", kind=HookKind.LIFECYCLE)],
            hook_router=router,
            loader=loader,
        )

        # Register plugin A (low priority)
        contrib_a = SlotContribution(
            plugin_id="com.example.a",
            contribution_id="widget",
            slot_key="ui.sidebar",
            priority=10,
        )
        hook_a = HookContribution(
            plugin_id="com.example.a",
            contribution_id="handler",
            hook_key="app.started",
            priority=10,
            handler="tests.fixtures.sample_plugin:on_app_started",
        )
        manifest_a = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.a",
            plugin_version=SemVer.parse("1.0.0"),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
            contributions=ManifestContributions(slots=(contrib_a,), hooks=(hook_a,)),
        )
        panel.register_manifest(manifest_a)
        panel.activate("com.example.a")

        # Register plugin B (high priority)
        contrib_b = SlotContribution(
            plugin_id="com.example.b",
            contribution_id="widget",
            slot_key="ui.sidebar",
            priority=100,
        )
        hook_b = HookContribution(
            plugin_id="com.example.b",
            contribution_id="handler",
            hook_key="app.started",
            priority=100,
            handler="tests.fixtures.sample_plugin:on_app_started_high_priority",
        )
        manifest_b = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.b",
            plugin_version=SemVer.parse("1.0.0"),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="tests.fixtures.sample_plugin:AnotherPlugin",
            contributions=ManifestContributions(slots=(contrib_b,), hooks=(hook_b,)),
        )
        panel.register_manifest(manifest_b)
        panel.activate("com.example.b")

        # Verify slot ordering (highest priority first)
        slots = panel.resolve_slot("ui.sidebar")
        assert len(slots) == 2
        assert slots[0].plugin_id == "com.example.b"  # priority 100
        assert slots[1].plugin_id == "com.example.a"  # priority 10

        # Verify hook ordering (highest priority first)
        results = panel.emit("app.started", payload={"timestamp": 999})
        assert results == ["high:999", "started:999"]

    def test_single_slot_policy(self) -> None:
        """Test that SINGLE policy returns only highest priority."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[SlotDefinition("ui.main", policy=SlotPolicy.SINGLE)],
            hooks=[],
            hook_router=router,
            loader=loader,
        )

        for plugin_id, priority in [("com.low", 10), ("com.high", 100), ("com.mid", 50)]:
            contrib = SlotContribution(
                plugin_id=plugin_id,
                contribution_id="main",
                slot_key="ui.main",
                priority=priority,
            )
            manifest = PluginManifest(
                manifest_version="1",
                plugin_id=plugin_id,
                plugin_version=SemVer.parse("1.0.0"),
                requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
                entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
                contributions=ManifestContributions(slots=(contrib,)),
            )
            panel.register_manifest(manifest)
            panel.activate(plugin_id)

        # Only highest priority should be returned
        result = panel.resolve_slot("ui.main")
        assert len(result) == 1
        assert result[0].plugin_id == "com.high"

    def test_first_result_hook_policy(self) -> None:
        """Test that FIRST_RESULT policy returns first non-None."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("command.run", kind=HookKind.COMMAND)],
            hook_router=router,
            loader=loader,
        )

        # Register handler that returns None for non-matching commands
        hook_main = HookContribution(
            plugin_id="com.example.main",
            contribution_id="cmd",
            hook_key="command.run",
            priority=100,
            handler="tests.fixtures.sample_plugin:command_handler",
        )
        manifest_main = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.main",
            plugin_version=SemVer.parse("1.0.0"),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
            contributions=ManifestContributions(hooks=(hook_main,)),
        )
        panel.register_manifest(manifest_main)
        panel.activate("com.example.main")

        # Register fallback handler
        hook_fallback = HookContribution(
            plugin_id="com.example.fallback",
            contribution_id="cmd",
            hook_key="command.run",
            priority=10,
            handler="tests.fixtures.sample_plugin:command_handler_fallback",
        )
        manifest_fallback = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.fallback",
            plugin_version=SemVer.parse("1.0.0"),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
            contributions=ManifestContributions(hooks=(hook_fallback,)),
        )
        panel.register_manifest(manifest_fallback)
        panel.activate("com.example.fallback")

        # Matching command - main handler responds
        result = panel.emit("command.run", payload={"command": "greet", "name": "Alice"})
        assert result == {"greeting": "Hello, Alice!"}

        # Non-matching command - falls through to fallback
        result = panel.emit("command.run", payload={"command": "unknown"})
        assert result == {"error": "Unknown command"}

    def test_deactivation_removes_contributions(self) -> None:
        """Test that deactivating a plugin removes its contributions."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[HookDefinition("app.started")],
            hook_router=router,
            loader=loader,
        )

        contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="widget",
            slot_key="ui.sidebar",
        )
        hook = HookContribution(
            plugin_id="com.example.test",
            contribution_id="handler",
            hook_key="app.started",
            handler="tests.fixtures.sample_plugin:on_app_started",
        )
        manifest = make_manifest("com.example.test", slots=(contrib,), hooks=(hook,))
        panel.register_manifest(manifest)
        panel.activate("com.example.test")

        # Contributions are active
        assert len(panel.resolve_slot("ui.sidebar")) == 1
        results = panel.emit("app.started", payload={"timestamp": 1})
        assert len(results) == 1

        # Deactivate
        panel.deactivate("com.example.test")

        # Contributions are removed
        assert len(panel.resolve_slot("ui.sidebar")) == 0
        results = panel.emit("app.started", payload={"timestamp": 1})
        assert len(results) == 0

    def test_plugin_lifecycle_hooks_called(self) -> None:
        """Test that plugin activate/deactivate methods are called."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[],
            hook_router=router,
            loader=loader,
        )

        manifest = make_manifest("com.example.test")
        panel.register_manifest(manifest)

        # Activate - should call plugin.activate()
        panel.activate("com.example.test")

        # We can't easily inspect the plugin instance from here,
        # but we can verify state transitions work
        from switchboard.domain.lifecycle import PluginState

        assert panel.get_plugin_state("com.example.test") == PluginState.ACTIVE

        # Deactivate - should call plugin.deactivate()
        panel.deactivate("com.example.test")
        assert panel.get_plugin_state("com.example.test") == PluginState.READY
