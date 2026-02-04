"""Tests for V2 activation planning features."""

from __future__ import annotations

import pytest

from switchboard import (
    ActivationPlan,
    HookDefinition,
    HookKind,
    PatchPanel,
    PluginManifest,
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
        ],
        hooks=[
            HookDefinition("app.started", kind=HookKind.LIFECYCLE),
        ],
        hook_router=MemoryHookRouter(),
        loader=ImportLoader(),
    )


def make_manifest(
    plugin_id: str,
    requires: tuple[str, ...] = (),
    optional_requires: tuple[str, ...] = (),
) -> PluginManifest:
    """Create a test manifest with dependencies."""
    return PluginManifest(
        manifest_version="1",
        plugin_id=plugin_id,
        plugin_version=SemVer(1, 0, 0),
        requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
        entrypoint="tests.fixtures.sample_plugin:SamplePlugin",
        contributions=ManifestContributions(),
        requires=requires,
        optional_requires=optional_requires,
    )


# =============================================================================
# activation_plan() Tests
# =============================================================================


class TestActivationPlan:
    """Tests for PatchPanel.activation_plan()."""

    def test_activation_plan_returns_activation_plan_type(self, panel: PatchPanel) -> None:
        """activation_plan() returns an ActivationPlan instance."""
        plan = panel.activation_plan()
        assert isinstance(plan, ActivationPlan)

    def test_activation_plan_empty_when_no_plugins(self, panel: PatchPanel) -> None:
        """Plan is empty when no plugins are registered."""
        plan = panel.activation_plan()
        assert plan.order == ()
        assert plan.blocked == {}
        assert plan.cycles == ()

    def test_activation_plan_single_plugin(self, panel: PatchPanel) -> None:
        """Single plugin with no dependencies."""
        panel.register_manifest(make_manifest("com.example.a"))
        plan = panel.activation_plan()

        assert plan.order == ("com.example.a",)
        assert plan.blocked == {}
        assert plan.cycles == ()

    def test_activation_plan_respects_dependencies(self, panel: PatchPanel) -> None:
        """Plugins are ordered by dependencies."""
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.a",)))
        panel.register_manifest(make_manifest("com.example.a"))
        plan = panel.activation_plan()

        # a must come before b
        assert plan.order.index("com.example.a") < plan.order.index("com.example.b")

    def test_activation_plan_alphabetical_tiebreak(self, panel: PatchPanel) -> None:
        """Independent plugins are ordered alphabetically."""
        panel.register_manifest(make_manifest("com.example.c"))
        panel.register_manifest(make_manifest("com.example.a"))
        panel.register_manifest(make_manifest("com.example.b"))
        plan = panel.activation_plan()

        assert plan.order == ("com.example.a", "com.example.b", "com.example.c")

    def test_activation_plan_missing_dependency(self, panel: PatchPanel) -> None:
        """Plugin with missing dependency is blocked."""
        panel.register_manifest(make_manifest("com.example.a", requires=("com.example.missing",)))
        plan = panel.activation_plan()

        assert plan.order == ()
        assert "com.example.a" in plan.blocked
        assert "missing" in plan.blocked["com.example.a"]

    def test_activation_plan_detects_cycle(self, panel: PatchPanel) -> None:
        """Circular dependencies are detected."""
        panel.register_manifest(make_manifest("com.example.a", requires=("com.example.b",)))
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.a",)))
        plan = panel.activation_plan()

        assert plan.order == ()
        assert "com.example.a" in plan.blocked
        assert "com.example.b" in plan.blocked
        assert len(plan.cycles) > 0

    def test_activation_plan_three_way_cycle(self, panel: PatchPanel) -> None:
        """Three-way circular dependency is detected."""
        panel.register_manifest(make_manifest("com.example.a", requires=("com.example.b",)))
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.c",)))
        panel.register_manifest(make_manifest("com.example.c", requires=("com.example.a",)))
        plan = panel.activation_plan()

        assert plan.order == ()
        assert len(plan.blocked) == 3
        assert len(plan.cycles) > 0

    def test_activation_plan_chain_dependency(self, panel: PatchPanel) -> None:
        """Chain of dependencies is ordered correctly."""
        panel.register_manifest(make_manifest("com.example.c", requires=("com.example.b",)))
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.a",)))
        panel.register_manifest(make_manifest("com.example.a"))
        plan = panel.activation_plan()

        assert plan.order == ("com.example.a", "com.example.b", "com.example.c")

    def test_activation_plan_optional_requires_affects_order(self, panel: PatchPanel) -> None:
        """optional_requires affects order but doesn't block if missing."""
        panel.register_manifest(
            make_manifest("com.example.b", optional_requires=("com.example.a",))
        )
        panel.register_manifest(make_manifest("com.example.a"))
        plan = panel.activation_plan()

        # a should come before b (optional dep exists)
        assert plan.order.index("com.example.a") < plan.order.index("com.example.b")

    def test_activation_plan_missing_optional_not_blocked(self, panel: PatchPanel) -> None:
        """Missing optional_requires does not block plugin."""
        panel.register_manifest(
            make_manifest("com.example.a", optional_requires=("com.example.missing",))
        )
        plan = panel.activation_plan()

        assert plan.order == ("com.example.a",)
        assert plan.blocked == {}

    def test_activation_plan_skips_already_active(self, panel: PatchPanel) -> None:
        """Already active plugins are not in the plan."""
        panel.register_manifest(make_manifest("com.example.a"))
        panel.activate("com.example.a")
        panel.register_manifest(make_manifest("com.example.b"))
        plan = panel.activation_plan()

        assert plan.order == ("com.example.b",)

    def test_activation_plan_diamond_dependency(self, panel: PatchPanel) -> None:
        """Diamond dependency pattern is handled correctly."""
        # d depends on b and c, both depend on a
        panel.register_manifest(make_manifest("com.example.a"))
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.a",)))
        panel.register_manifest(make_manifest("com.example.c", requires=("com.example.a",)))
        panel.register_manifest(
            make_manifest("com.example.d", requires=("com.example.b", "com.example.c"))
        )
        plan = panel.activation_plan()

        # a first, then b and c (alphabetical), then d
        assert plan.order[0] == "com.example.a"
        assert plan.order[-1] == "com.example.d"
        assert set(plan.order[1:3]) == {"com.example.b", "com.example.c"}


# =============================================================================
# activate_all() Tests
# =============================================================================


class TestActivateAll:
    """Tests for PatchPanel.activate_all()."""

    def test_activate_all_returns_plan(self, panel: PatchPanel) -> None:
        """activate_all() returns an ActivationPlan."""
        plan = panel.activate_all()
        assert isinstance(plan, ActivationPlan)

    def test_activate_all_activates_single_plugin(self, panel: PatchPanel) -> None:
        """Single plugin is activated."""
        panel.register_manifest(make_manifest("com.example.a"))
        plan = panel.activate_all()

        assert plan.order == ("com.example.a",)
        assert panel.get_plugin_state("com.example.a").value == "active"

    def test_activate_all_respects_dependency_order(self, panel: PatchPanel) -> None:
        """Plugins are activated in dependency order."""
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.a",)))
        panel.register_manifest(make_manifest("com.example.a"))
        plan = panel.activate_all()

        assert plan.order.index("com.example.a") < plan.order.index("com.example.b")
        assert panel.get_plugin_state("com.example.a").value == "active"
        assert panel.get_plugin_state("com.example.b").value == "active"

    def test_activate_all_blocks_on_missing_dependency(self, panel: PatchPanel) -> None:
        """Plugin with missing dependency is not activated."""
        panel.register_manifest(make_manifest("com.example.a", requires=("com.example.missing",)))
        plan = panel.activate_all()

        assert plan.order == ()
        assert "com.example.a" in plan.blocked
        assert panel.get_plugin_state("com.example.a").value == "ready"

    def test_activate_all_partial_success(self, panel: PatchPanel) -> None:
        """Independent plugins activate even if one has issues."""
        panel.register_manifest(make_manifest("com.example.a"))
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.missing",)))
        plan = panel.activate_all()

        assert "com.example.a" in plan.order
        assert "com.example.b" in plan.blocked
        assert panel.get_plugin_state("com.example.a").value == "active"

    def test_activate_all_dependent_blocked_on_failure(self, panel: PatchPanel) -> None:
        """Dependent plugins are blocked when dependency fails."""
        # Create a plugin that will fail activation
        bad_manifest = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.bad",
            plugin_version=SemVer(1, 0, 0),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="nonexistent.module:BadPlugin",  # This will fail
            contributions=ManifestContributions(),
        )
        panel.register_manifest(bad_manifest)
        panel.register_manifest(
            make_manifest("com.example.dependent", requires=("com.example.bad",))
        )

        plan = panel.activate_all()

        assert "com.example.bad" in plan.blocked
        assert "com.example.dependent" in plan.blocked
        assert "activation failed" in plan.blocked["com.example.bad"]

    def test_activate_all_no_rollback_on_later_failure(self, panel: PatchPanel) -> None:
        """Earlier successful activations are not rolled back."""
        panel.register_manifest(make_manifest("com.example.first"))
        bad_manifest = PluginManifest(
            manifest_version="1",
            plugin_id="com.example.second",
            plugin_version=SemVer(1, 0, 0),
            requires_switchboard=ApiRange.parse(">=0.1.0,<1.0.0"),
            entrypoint="nonexistent.module:BadPlugin",
            contributions=ManifestContributions(),
        )
        panel.register_manifest(bad_manifest)

        plan = panel.activate_all()

        # First should remain active
        assert "com.example.first" in plan.order
        assert panel.get_plugin_state("com.example.first").value == "active"
        # Second failed
        assert "com.example.second" in plan.blocked

    def test_activate_all_idempotent(self, panel: PatchPanel) -> None:
        """Calling activate_all() twice doesn't re-activate."""
        panel.register_manifest(make_manifest("com.example.a"))

        plan1 = panel.activate_all()
        plan2 = panel.activate_all()

        assert plan1.order == ("com.example.a",)
        assert plan2.order == ()  # Already active, not in plan

    def test_activate_all_with_cycles(self, panel: PatchPanel) -> None:
        """Plugins in cycles are blocked."""
        panel.register_manifest(make_manifest("com.example.a", requires=("com.example.b",)))
        panel.register_manifest(make_manifest("com.example.b", requires=("com.example.a",)))
        panel.register_manifest(make_manifest("com.example.c"))  # Independent

        plan = panel.activate_all()

        # c should activate
        assert "com.example.c" in plan.order
        assert panel.get_plugin_state("com.example.c").value == "active"
        # a and b blocked due to cycle
        assert "com.example.a" in plan.blocked
        assert "com.example.b" in plan.blocked
