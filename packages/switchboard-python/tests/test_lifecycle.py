"""Tests for plugin lifecycle state machine."""

import pytest

from switchboard import LifecycleError
from switchboard.domain.lifecycle import PluginLifecycle, PluginState


class TestPluginLifecycle:
    """Tests for PluginLifecycle state machine."""

    def test_initial_state_is_ready(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        assert lifecycle.state == PluginState.READY
        assert not lifecycle.is_active
        assert not lifecycle.is_failed

    def test_activation_flow(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")

        # READY -> STARTING
        lifecycle.begin_activation()
        assert lifecycle.state == PluginState.STARTING

        # STARTING -> ACTIVE
        lifecycle.complete_activation()
        assert lifecycle.state == PluginState.ACTIVE
        assert lifecycle.is_active

    def test_deactivation_flow(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()
        lifecycle.complete_activation()

        # ACTIVE -> STOPPING
        lifecycle.begin_deactivation()
        assert lifecycle.state == PluginState.STOPPING

        # STOPPING -> READY
        lifecycle.complete_deactivation()
        assert lifecycle.state == PluginState.READY
        assert not lifecycle.is_active

    def test_activation_from_wrong_state_raises(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()  # Now in STARTING

        with pytest.raises(LifecycleError) as exc_info:
            lifecycle.begin_activation()

        assert exc_info.value.plugin_id == "com.example.plugin"
        assert exc_info.value.operation == "activate"
        assert exc_info.value.current_state == "starting"

    def test_deactivation_from_wrong_state_raises(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")

        with pytest.raises(LifecycleError) as exc_info:
            lifecycle.begin_deactivation()

        assert exc_info.value.operation == "deactivate"
        assert exc_info.value.current_state == "ready"

    def test_rollback_from_starting(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()

        lifecycle.rollback()
        assert lifecycle.state == PluginState.READY

    def test_rollback_from_wrong_state_raises(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")

        with pytest.raises(LifecycleError) as exc_info:
            lifecycle.rollback()

        assert exc_info.value.operation == "rollback"

    def test_fail_from_starting(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()

        error = RuntimeError("Import failed")
        lifecycle.fail(error)

        assert lifecycle.state == PluginState.FAILED
        assert lifecycle.is_failed
        assert lifecycle.last_error is error

    def test_fail_from_active(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()
        lifecycle.complete_activation()

        error = RuntimeError("Runtime crash")
        lifecycle.fail(error)

        assert lifecycle.state == PluginState.FAILED
        assert lifecycle.last_error is error

    def test_fail_clears_instance(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()
        lifecycle.instance = object()
        lifecycle.complete_activation()

        lifecycle.fail(RuntimeError("crash"))
        assert lifecycle.instance is None

    def test_reset_from_failed(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()
        lifecycle.fail(RuntimeError("error"))

        lifecycle.reset()
        assert lifecycle.state == PluginState.READY
        assert lifecycle.last_error is None

    def test_reset_from_wrong_state_raises(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")

        with pytest.raises(LifecycleError) as exc_info:
            lifecycle.reset()

        assert exc_info.value.operation == "reset"

    def test_instance_property(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        assert lifecycle.instance is None

        instance = object()
        lifecycle.instance = instance
        assert lifecycle.instance is instance

    def test_complete_deactivation_clears_instance(self) -> None:
        lifecycle = PluginLifecycle("com.example.plugin")
        lifecycle.begin_activation()
        lifecycle.instance = object()
        lifecycle.complete_activation()

        lifecycle.begin_deactivation()
        lifecycle.complete_deactivation()

        assert lifecycle.instance is None
