"""Tests for Pluggy-based hook router.

These tests mirror the MemoryHookRouter tests to ensure both implementations
behave identically.
"""

import pytest

from switchboard import HookContribution, HookPolicy
from switchboard.adapters.hook_router_pluggy import PluggyHookRouter


class TestPluggyHookRouter:
    """Tests for PluggyHookRouter."""

    def test_register_and_emit_broadcast(self) -> None:
        """Test registering handlers and emitting with broadcast policy."""
        router = PluggyHookRouter()

        results_captured: list[str] = []

        def handler1(payload: dict, context: dict) -> str:
            results_captured.append("h1")
            return "result1"

        def handler2(payload: dict, context: dict) -> str:
            results_captured.append("h2")
            return "result2"

        contrib1 = HookContribution(
            plugin_id="plugin.a",
            contribution_id="h1",
            hook_key="test.hook",
            priority=50,
        )
        contrib2 = HookContribution(
            plugin_id="plugin.b",
            contribution_id="h2",
            hook_key="test.hook",
            priority=100,
        )

        router.register_handler("test.hook", contrib1, handler1)
        router.register_handler("test.hook", contrib2, handler2)

        results = router.emit("test.hook", HookPolicy.BROADCAST, {}, None)

        # Higher priority first
        assert results_captured == ["h2", "h1"]
        assert results == ["result2", "result1"]

    def test_emit_first_result_returns_first_non_none(self) -> None:
        """Test first_result policy returns first non-None value."""
        router = PluggyHookRouter()

        def returns_none(payload: dict, context: dict) -> None:
            return None

        def returns_value(payload: dict, context: dict) -> str:
            return "found"

        def should_not_be_called(payload: dict, context: dict) -> str:
            raise AssertionError("Should not be called")

        contrib1 = HookContribution(
            plugin_id="a", contribution_id="h1", hook_key="cmd", priority=100
        )
        contrib2 = HookContribution(
            plugin_id="b", contribution_id="h2", hook_key="cmd", priority=50
        )
        contrib3 = HookContribution(
            plugin_id="c", contribution_id="h3", hook_key="cmd", priority=10
        )

        router.register_handler("cmd", contrib1, returns_none)
        router.register_handler("cmd", contrib2, returns_value)
        router.register_handler("cmd", contrib3, should_not_be_called)

        result = router.emit("cmd", HookPolicy.FIRST_RESULT, {}, None)
        assert result == "found"

    def test_emit_first_result_all_none(self) -> None:
        """Test first_result returns None if all handlers return None."""
        router = PluggyHookRouter()

        def returns_none(payload: dict, context: dict) -> None:
            return None

        contrib = HookContribution(plugin_id="a", contribution_id="h1", hook_key="cmd", priority=50)
        router.register_handler("cmd", contrib, returns_none)

        result = router.emit("cmd", HookPolicy.FIRST_RESULT, {}, None)
        assert result is None

    def test_emit_empty_hook(self) -> None:
        """Test emitting to a hook with no handlers."""
        router = PluggyHookRouter()

        broadcast_result = router.emit("empty", HookPolicy.BROADCAST, {}, None)
        assert broadcast_result == []

        first_result = router.emit("empty", HookPolicy.FIRST_RESULT, {}, None)
        assert first_result is None

    def test_unregister_handler(self) -> None:
        """Test unregistering a handler."""
        router = PluggyHookRouter()

        def handler(payload: dict, context: dict) -> str:
            return "result"

        contrib = HookContribution(
            plugin_id="a", contribution_id="h1", hook_key="test", priority=50
        )
        router.register_handler("test", contrib, handler)

        # Handler is registered
        assert router.emit("test", HookPolicy.BROADCAST, {}, None) == ["result"]

        # Unregister
        router.unregister_handler("test", "h1")

        # Handler is gone
        assert router.emit("test", HookPolicy.BROADCAST, {}, None) == []

    def test_unregister_nonexistent_hook(self) -> None:
        """Test unregistering from a nonexistent hook doesn't raise."""
        router = PluggyHookRouter()
        router.unregister_handler("nonexistent", "h1")  # Should not raise

    def test_clear(self) -> None:
        """Test clearing all handlers."""
        router = PluggyHookRouter()

        def handler(payload: dict, context: dict) -> str:
            return "result"

        contrib = HookContribution(
            plugin_id="a", contribution_id="h1", hook_key="test", priority=50
        )
        router.register_handler("test", contrib, handler)

        router.clear()

        assert router.emit("test", HookPolicy.BROADCAST, {}, None) == []

    def test_broadcast_continues_on_error(self) -> None:
        """Test that broadcast continues even if a handler raises."""
        router = PluggyHookRouter()

        def raises_error(payload: dict, context: dict) -> str:
            raise ValueError("boom")

        def returns_value(payload: dict, context: dict) -> str:
            return "success"

        contrib1 = HookContribution(
            plugin_id="a", contribution_id="h1", hook_key="test", priority=100
        )
        contrib2 = HookContribution(
            plugin_id="b", contribution_id="h2", hook_key="test", priority=50
        )

        router.register_handler("test", contrib1, raises_error)
        router.register_handler("test", contrib2, returns_value)

        # Should continue despite error
        results = router.emit("test", HookPolicy.BROADCAST, {}, None)
        assert results == ["success"]

    def test_first_result_propagates_error(self) -> None:
        """Test that first_result propagates exceptions."""
        router = PluggyHookRouter()

        def raises_error(payload: dict, context: dict) -> str:
            raise ValueError("boom")

        contrib = HookContribution(
            plugin_id="a", contribution_id="h1", hook_key="test", priority=50
        )
        router.register_handler("test", contrib, raises_error)

        with pytest.raises(ValueError, match="boom"):
            router.emit("test", HookPolicy.FIRST_RESULT, {}, None)

    def test_ordering_tiebreak(self) -> None:
        """Test ordering tiebreak by plugin_id then contribution_id."""
        router = PluggyHookRouter()
        call_order: list[str] = []

        def make_handler(name: str):
            def handler(payload: dict, context: dict) -> str:
                call_order.append(name)
                return name

            return handler

        # Same priority, different plugin_ids
        for plugin_id in ["z.plugin", "a.plugin", "m.plugin"]:
            contrib = HookContribution(
                plugin_id=plugin_id,
                contribution_id="handler",
                hook_key="test",
                priority=50,
            )
            router.register_handler("test", contrib, make_handler(plugin_id))

        router.emit("test", HookPolicy.BROADCAST, {}, None)

        # Should be alphabetical by plugin_id
        assert call_order == ["a.plugin", "m.plugin", "z.plugin"]


class TestPluggyNoLeakage:
    """Tests that verify Pluggy types don't leak into domain."""

    def test_no_pluggy_in_domain_imports(self) -> None:
        """Verify pluggy is not imported in domain modules."""
        import switchboard.domain.errors as errors
        import switchboard.domain.lifecycle as lifecycle
        import switchboard.domain.models as models
        import switchboard.domain.patch_panel as patch_panel
        import switchboard.domain.ports as ports

        for module in [errors, lifecycle, models, patch_panel, ports]:
            # Check that pluggy is not in the module's namespace
            module_dict = vars(module)
            assert "pluggy" not in module_dict, f"pluggy found in {module.__name__}"

            # Check that the module doesn't directly import pluggy
            # by verifying pluggy isn't in its __dict__
            for attr_name, attr_value in module_dict.items():
                if hasattr(attr_value, "__module__") and attr_value.__module__:
                    assert not attr_value.__module__.startswith("pluggy"), (
                        f"pluggy type {attr_name} found in {module.__name__}"
                    )
