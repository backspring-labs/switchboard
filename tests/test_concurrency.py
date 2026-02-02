"""Tests for concurrency contract.

Per the V1 plan:
- register_manifest(), activate(), deactivate() acquire an exclusive lock
- resolve_slot(), emit() acquire a shared lock (currently RLock - exclusive)
- Calling register_manifest() or activate() from within a hook handler raises LifecycleError
"""

import threading
import time

from switchboard import (
    ApiRange,
    HookContribution,
    HookDefinition,
    LifecycleError,
    ManifestContributions,
    PatchPanel,
    PluginManifest,
    SemVer,
    SlotDefinition,
)
from switchboard.adapters.hook_router_memory import MemoryHookRouter
from switchboard.adapters.loader import ImportLoader


def make_manifest(
    plugin_id: str = "com.example.test",
    hooks: tuple[HookContribution, ...] = (),
) -> PluginManifest:
    """Create a test manifest."""
    return PluginManifest(
        manifest_version="1",
        plugin_id=plugin_id,
        plugin_version=SemVer.parse("1.0.0"),
        requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
        entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
        contributions=ManifestContributions(hooks=hooks),
    )


class TestReentrancyProtection:
    """Tests for re-entrancy protection from within hook handlers.

    Note: With broadcast policy, exceptions in handlers are logged but not propagated.
    We verify that the mutation was prevented (the handler's action had no effect).
    """

    def test_register_manifest_from_hook_prevented(self) -> None:
        """register_manifest() from within a hook handler is prevented."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("test.hook")],
            hook_router=router,
            loader=loader,
        )

        error_raised: list[Exception] = []

        def malicious_handler(payload: dict, context: dict) -> None:
            try:
                panel.register_manifest(make_manifest(plugin_id="com.example.sneaky"))
            except LifecycleError as e:
                error_raised.append(e)
                raise

        hook_contrib = HookContribution(
            plugin_id="com.example.test",
            contribution_id="handler",
            hook_key="test.hook",
            handler="tests.fixtures.sample_plugin:on_app_started",
        )
        manifest = make_manifest(hooks=(hook_contrib,))
        panel.register_manifest(manifest)
        panel.activate("com.example.test")

        router.register_handler(
            "test.hook",
            HookContribution(
                plugin_id="com.example.test",
                contribution_id="malicious",
                hook_key="test.hook",
                priority=100,
            ),
            malicious_handler,
        )

        # Emit - broadcast policy swallows the exception but we captured it
        panel.emit("test.hook", payload={})

        # Verify the LifecycleError was raised
        assert len(error_raised) == 1
        assert "in_hook_emission" in str(error_raised[0])

        # Verify the sneaky plugin was NOT registered
        assert "com.example.sneaky" not in panel.list_plugins()

    def test_activate_from_hook_prevented(self) -> None:
        """activate() from within a hook handler is prevented."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("test.hook")],
            hook_router=router,
            loader=loader,
        )

        panel.register_manifest(make_manifest(plugin_id="com.example.first"))
        panel.register_manifest(make_manifest(plugin_id="com.example.second"))
        panel.activate("com.example.first")

        error_raised: list[Exception] = []

        def malicious_handler(payload: dict, context: dict) -> None:
            try:
                panel.activate("com.example.second")
            except LifecycleError as e:
                error_raised.append(e)
                raise

        router.register_handler(
            "test.hook",
            HookContribution(
                plugin_id="com.example.first",
                contribution_id="malicious",
                hook_key="test.hook",
            ),
            malicious_handler,
        )

        panel.emit("test.hook", payload={})

        # Verify the LifecycleError was raised
        assert len(error_raised) == 1
        assert "in_hook_emission" in str(error_raised[0])

        # Verify the second plugin was NOT activated
        from switchboard.domain.lifecycle import PluginState

        assert panel.get_plugin_state("com.example.second") == PluginState.READY

    def test_deactivate_from_hook_prevented(self) -> None:
        """deactivate() from within a hook handler is prevented."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("test.hook")],
            hook_router=router,
            loader=loader,
        )

        panel.register_manifest(make_manifest(plugin_id="com.example.test"))
        panel.activate("com.example.test")

        error_raised: list[Exception] = []

        def malicious_handler(payload: dict, context: dict) -> None:
            try:
                panel.deactivate("com.example.test")
            except LifecycleError as e:
                error_raised.append(e)
                raise

        router.register_handler(
            "test.hook",
            HookContribution(
                plugin_id="com.example.test",
                contribution_id="malicious",
                hook_key="test.hook",
            ),
            malicious_handler,
        )

        panel.emit("test.hook", payload={})

        # Verify the LifecycleError was raised
        assert len(error_raised) == 1
        assert "in_hook_emission" in str(error_raised[0])

        # Verify the plugin is still active
        from switchboard.domain.lifecycle import PluginState

        assert panel.get_plugin_state("com.example.test") == PluginState.ACTIVE


class TestThreadSafety:
    """Tests for thread safety of PatchPanel operations."""

    def test_concurrent_resolve_slot(self) -> None:
        """Multiple threads can resolve slots concurrently."""
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[SlotDefinition("ui.sidebar")],
            hooks=[],
            hook_router=router,
            loader=loader,
        )

        results: list[int] = []
        errors: list[Exception] = []

        def resolve_many_times(n: int) -> None:
            try:
                for _ in range(n):
                    panel.resolve_slot("ui.sidebar")
                results.append(n)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=resolve_many_times, args=(100,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5

    def test_emit_during_activate_blocks_or_succeeds(self) -> None:
        """emit() from another thread during activate() should block until activate completes.

        This test verifies that the locking mechanism works correctly.
        Since we use RLock (not RWLock), emit() will block until activate() releases the lock.
        """
        router = MemoryHookRouter()
        loader = ImportLoader()

        panel = PatchPanel(
            slots=[],
            hooks=[HookDefinition("test.hook")],
            hook_router=router,
            loader=loader,
        )

        panel.register_manifest(make_manifest(plugin_id="com.example.test"))

        # Track operation order
        operation_log: list[str] = []
        activation_started = threading.Event()
        activation_can_complete = threading.Event()

        # Patch the loader to add a delay during activation
        original_load = loader.load_entrypoint

        def slow_load(entrypoint: str) -> object:
            operation_log.append("activate_start")
            activation_started.set()
            # Wait for signal to complete (simulates slow activation)
            activation_can_complete.wait(timeout=2.0)
            result = original_load(entrypoint)
            operation_log.append("activate_end")
            return result

        loader.load_entrypoint = slow_load  # type: ignore[method-assign]

        emit_result: list[object] = []
        emit_error: list[Exception] = []

        def emit_thread() -> None:
            try:
                # Wait for activation to start
                activation_started.wait(timeout=2.0)
                # Small delay to ensure we're in the middle of activation
                time.sleep(0.01)
                operation_log.append("emit_attempt")
                result = panel.emit("test.hook", payload={})
                operation_log.append("emit_complete")
                emit_result.append(result)
            except Exception as e:
                emit_error.append(e)

        # Start emit thread
        t = threading.Thread(target=emit_thread)
        t.start()

        # Start activation (will block on slow_load)
        activate_thread = threading.Thread(target=lambda: panel.activate("com.example.test"))
        activate_thread.start()

        # Wait for activation to start
        activation_started.wait(timeout=2.0)
        time.sleep(0.05)  # Give emit thread time to attempt

        # Allow activation to complete
        activation_can_complete.set()

        # Wait for both threads
        activate_thread.join(timeout=2.0)
        t.join(timeout=2.0)

        # Verify no errors
        assert len(emit_error) == 0, f"Emit raised: {emit_error}"

        # The emit should have completed after activation
        # (either blocked and waited, or happened after)
        assert "emit_complete" in operation_log
        assert "activate_end" in operation_log

        # Due to locking, emit should complete after activate_end
        # (the lock ensures emit waits for activation to finish)
        activate_end_idx = operation_log.index("activate_end")
        emit_complete_idx = operation_log.index("emit_complete")
        assert emit_complete_idx > activate_end_idx, (
            f"emit should complete after activate, got: {operation_log}"
        )
