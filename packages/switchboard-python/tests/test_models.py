"""Tests for domain models - value objects and entities."""

import pytest

from switchboard import (
    ApiRange,
    HookContribution,
    HookDefinition,
    HookKind,
    HookPolicy,
    ManifestContributions,
    PluginManifest,
    SemVer,
    SlotContribution,
    SlotDefinition,
    SlotPolicy,
)


class TestSemVer:
    """Tests for SemVer value object."""

    def test_parse_valid_version(self) -> None:
        v = SemVer.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_with_whitespace(self) -> None:
        v = SemVer.parse("  1.2.3  ")
        assert v == SemVer(1, 2, 3)

    def test_parse_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            SemVer.parse("1.2")

    def test_parse_non_numeric(self) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            SemVer.parse("1.2.x")

    def test_str(self) -> None:
        assert str(SemVer(1, 2, 3)) == "1.2.3"

    def test_comparison_lt(self) -> None:
        assert SemVer(1, 0, 0) < SemVer(2, 0, 0)
        assert SemVer(1, 0, 0) < SemVer(1, 1, 0)
        assert SemVer(1, 0, 0) < SemVer(1, 0, 1)

    def test_comparison_le(self) -> None:
        assert SemVer(1, 0, 0) <= SemVer(1, 0, 0)
        assert SemVer(1, 0, 0) <= SemVer(2, 0, 0)

    def test_comparison_gt(self) -> None:
        assert SemVer(2, 0, 0) > SemVer(1, 0, 0)
        assert SemVer(1, 1, 0) > SemVer(1, 0, 0)

    def test_comparison_ge(self) -> None:
        assert SemVer(1, 0, 0) >= SemVer(1, 0, 0)
        assert SemVer(2, 0, 0) >= SemVer(1, 0, 0)

    def test_equality(self) -> None:
        assert SemVer(1, 2, 3) == SemVer(1, 2, 3)
        assert SemVer(1, 2, 3) != SemVer(1, 2, 4)

    def test_frozen(self) -> None:
        v = SemVer(1, 2, 3)
        with pytest.raises(AttributeError):
            v.major = 2  # type: ignore[misc]


class TestApiRange:
    """Tests for ApiRange value object."""

    def test_parse_single_constraint(self) -> None:
        r = ApiRange.parse(">=1.0.0")
        assert len(r.constraints) == 1
        assert r.constraints[0] == (">=", SemVer(1, 0, 0))

    def test_parse_multiple_constraints(self) -> None:
        r = ApiRange.parse(">=1.0.0,<2.0.0")
        assert len(r.constraints) == 2
        assert r.constraints[0] == (">=", SemVer(1, 0, 0))
        assert r.constraints[1] == ("<", SemVer(2, 0, 0))

    def test_parse_with_whitespace(self) -> None:
        r = ApiRange.parse(">= 1.0.0 , < 2.0.0")
        assert r.contains(SemVer(1, 5, 0))

    def test_parse_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty version range"):
            ApiRange.parse("")

    def test_parse_invalid_constraint(self) -> None:
        with pytest.raises(ValueError, match="Invalid constraint"):
            ApiRange.parse("~1.0.0")

    def test_contains_gte(self) -> None:
        r = ApiRange.parse(">=1.0.0")
        assert r.contains(SemVer(1, 0, 0))
        assert r.contains(SemVer(2, 0, 0))
        assert not r.contains(SemVer(0, 9, 0))

    def test_contains_lt(self) -> None:
        r = ApiRange.parse("<2.0.0")
        assert r.contains(SemVer(1, 9, 9))
        assert not r.contains(SemVer(2, 0, 0))

    def test_contains_range(self) -> None:
        r = ApiRange.parse(">=0.1.0,<1.0.0")
        assert r.contains(SemVer(0, 1, 0))
        assert r.contains(SemVer(0, 5, 0))
        assert not r.contains(SemVer(0, 0, 9))
        assert not r.contains(SemVer(1, 0, 0))

    def test_contains_exact(self) -> None:
        r = ApiRange.parse("==1.2.3")
        assert r.contains(SemVer(1, 2, 3))
        assert not r.contains(SemVer(1, 2, 4))

    def test_str(self) -> None:
        r = ApiRange.parse(">=1.0.0,<2.0.0")
        assert str(r) == ">=1.0.0,<2.0.0"


class TestSlotDefinition:
    """Tests for SlotDefinition entity."""

    def test_create_with_defaults(self) -> None:
        slot = SlotDefinition("ui.sidebar")
        assert slot.slot_key == "ui.sidebar"
        assert slot.policy == SlotPolicy.MULTI
        assert slot.description == ""

    def test_create_single_policy(self) -> None:
        slot = SlotDefinition("ui.main", policy=SlotPolicy.SINGLE)
        assert slot.policy == SlotPolicy.SINGLE

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="slot_key cannot be empty"):
            SlotDefinition("")


class TestHookDefinition:
    """Tests for HookDefinition entity."""

    def test_create_with_defaults(self) -> None:
        hook = HookDefinition("app.started")
        assert hook.hook_key == "app.started"
        assert hook.kind == HookKind.EVENT
        assert hook.policy is None

    def test_effective_policy_from_kind(self) -> None:
        event_hook = HookDefinition("event.foo", kind=HookKind.EVENT)
        assert event_hook.effective_policy == HookPolicy.BROADCAST

        command_hook = HookDefinition("cmd.foo", kind=HookKind.COMMAND)
        assert command_hook.effective_policy == HookPolicy.FIRST_RESULT

        lifecycle_hook = HookDefinition("life.foo", kind=HookKind.LIFECYCLE)
        assert lifecycle_hook.effective_policy == HookPolicy.BROADCAST

    def test_effective_policy_explicit_override(self) -> None:
        hook = HookDefinition("cmd.foo", kind=HookKind.COMMAND, policy=HookPolicy.BROADCAST)
        assert hook.effective_policy == HookPolicy.BROADCAST

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="hook_key cannot be empty"):
            HookDefinition("")


class TestSlotContribution:
    """Tests for SlotContribution entity."""

    def test_create_minimal(self) -> None:
        contrib = SlotContribution(
            plugin_id="com.example.plugin",
            contribution_id="my.contrib",
            slot_key="ui.sidebar",
        )
        assert contrib.priority == 50
        assert contrib.factory == ""
        assert contrib.metadata == {}

    def test_create_full(self) -> None:
        contrib = SlotContribution(
            plugin_id="com.example.plugin",
            contribution_id="my.contrib",
            slot_key="ui.sidebar",
            priority=100,
            factory="my_plugin:build_widget",
            metadata={"icon": "star"},
        )
        assert contrib.priority == 100
        assert contrib.factory == "my_plugin:build_widget"

    def test_empty_plugin_id_raises(self) -> None:
        with pytest.raises(ValueError):
            SlotContribution(plugin_id="", contribution_id="x", slot_key="y")


class TestHookContribution:
    """Tests for HookContribution entity."""

    def test_create_minimal(self) -> None:
        contrib = HookContribution(
            plugin_id="com.example.plugin",
            contribution_id="my.handler",
            hook_key="app.started",
        )
        assert contrib.priority == 50
        assert contrib.handler == ""


class TestPluginManifest:
    """Tests for PluginManifest entity."""

    def test_create_minimal(self) -> None:
        manifest = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.test",
            plugin_version=SemVer(1, 0, 0),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="test_plugin:TestPlugin",
        )
        assert manifest.name == ""
        assert manifest.contributions.slots == ()
        assert manifest.contributions.hooks == ()

    def test_create_with_contributions(self) -> None:
        slot_contrib = SlotContribution(
            plugin_id="com.example.test",
            contribution_id="sidebar",
            slot_key="ui.sidebar",
        )
        hook_contrib = HookContribution(
            plugin_id="com.example.test",
            contribution_id="startup",
            hook_key="app.started",
        )
        manifest = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.test",
            plugin_version=SemVer(1, 0, 0),
            requires_switchboard=ApiRange.parse(">=0.1.0"),
            entrypoint="test_plugin:TestPlugin",
            contributions=ManifestContributions(
                slots=(slot_contrib,),
                hooks=(hook_contrib,),
            ),
        )
        assert len(manifest.contributions.slots) == 1
        assert len(manifest.contributions.hooks) == 1

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValueError, match="manifest_version is required"):
            PluginManifest(
                manifest_version="",
                plugin_id="com.example.test",
                plugin_version=SemVer(1, 0, 0),
                requires_switchboard=ApiRange.parse(">=0.1.0"),
                entrypoint="test:Test",
            )
