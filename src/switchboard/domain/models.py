"""Switchboard domain models - value objects and entities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003 - used at runtime in dataclass field
from enum import Enum
from typing import Any

# =============================================================================
# Value Objects
# =============================================================================


@dataclass(frozen=True, slots=True)
class SemVer:
    """Semantic version (major.minor.patch)."""

    major: int
    minor: int
    patch: int

    _PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

    @classmethod
    def parse(cls, version_str: str) -> SemVer:
        """Parse a version string like '1.2.3' into a SemVer."""
        match = cls._PATTERN.match(version_str.strip())
        if not match:
            raise ValueError(f"Invalid version format: {version_str!r} (expected X.Y.Z)")
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)


@dataclass(frozen=True, slots=True)
class ApiRange:
    """A version range for compatibility checking (e.g., '>=0.1,<1')."""

    constraints: tuple[tuple[str, SemVer], ...]

    _CONSTRAINT_PATTERN = re.compile(r"(>=|<=|>|<|==)\s*(\d+\.\d+\.\d+)")

    @classmethod
    def parse(cls, range_str: str) -> ApiRange:
        """Parse a range string like '>=0.1.0,<1.0.0' into an ApiRange."""
        constraints: list[tuple[str, SemVer]] = []
        for part in range_str.split(","):
            part = part.strip()
            if not part:
                continue
            match = cls._CONSTRAINT_PATTERN.match(part)
            if not match:
                raise ValueError(f"Invalid constraint format: {part!r}")
            op = match.group(1)
            version = SemVer.parse(match.group(2))
            constraints.append((op, version))
        if not constraints:
            raise ValueError(f"Empty version range: {range_str!r}")
        return cls(constraints=tuple(constraints))

    def contains(self, version: SemVer) -> bool:
        """Check if a version satisfies all constraints in this range."""
        ops = {
            ">=": lambda v, c: v >= c,
            "<=": lambda v, c: v <= c,
            ">": lambda v, c: v > c,
            "<": lambda v, c: v < c,
            "==": lambda v, c: v == c,
        }
        for op, constraint_version in self.constraints:
            if not ops[op](version, constraint_version):
                return False
        return True

    def __str__(self) -> str:
        return ",".join(f"{op}{version}" for op, version in self.constraints)


# =============================================================================
# Enums
# =============================================================================


class SlotPolicy(Enum):
    """Policy for how many contributions a slot accepts."""

    MULTI = "multi"  # Multiple contributions allowed (default)
    SINGLE = "single"  # Only highest-priority contribution used


class HookKind(Enum):
    """The kind of hook, which determines default dispatch policy."""

    EVENT = "event"  # Broadcast to all handlers
    COMMAND = "command"  # First result wins
    LIFECYCLE = "lifecycle"  # Broadcast to all handlers


class HookPolicy(Enum):
    """Policy for how hook handlers are invoked."""

    BROADCAST = "broadcast"  # Call all handlers, collect results
    FIRST_RESULT = "first_result"  # Stop on first non-None result


# =============================================================================
# Entities
# =============================================================================


@dataclass(frozen=True, slots=True)
class SlotDefinition:
    """Host-defined slot where contributions can attach."""

    slot_key: str
    policy: SlotPolicy = SlotPolicy.MULTI
    description: str = ""

    def __post_init__(self) -> None:
        if not self.slot_key:
            raise ValueError("slot_key cannot be empty")


@dataclass(frozen=True, slots=True)
class HookDefinition:
    """Host-defined hook for event/command interception."""

    hook_key: str
    kind: HookKind = HookKind.EVENT
    policy: HookPolicy | None = None  # None means derive from kind
    description: str = ""

    def __post_init__(self) -> None:
        if not self.hook_key:
            raise ValueError("hook_key cannot be empty")

    @property
    def effective_policy(self) -> HookPolicy:
        """Get the effective policy, deriving from kind if not explicitly set."""
        if self.policy is not None:
            return self.policy
        if self.kind == HookKind.COMMAND:
            return HookPolicy.FIRST_RESULT
        return HookPolicy.BROADCAST


@dataclass(frozen=True, kw_only=True)
class Contribution:
    """Base class for all plugin contributions.

    This is the stable public unit of extensibility. All contribution types
    (slots, hooks, and future kinds) inherit from this base.
    """

    plugin_id: str
    contribution_id: str
    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plugin_id:
            raise ValueError("plugin_id cannot be empty")
        if not self.contribution_id:
            raise ValueError("contribution_id cannot be empty")


@dataclass(frozen=True, kw_only=True)
class SlotContribution(Contribution):
    """A plugin's contribution to a slot."""

    slot_key: str
    factory: str = ""  # Import path to callable

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.slot_key:
            raise ValueError("slot_key cannot be empty")


@dataclass(frozen=True, kw_only=True)
class HookContribution(Contribution):
    """A plugin's contribution to a hook."""

    hook_key: str
    handler: str = ""  # Import path to callable

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.hook_key:
            raise ValueError("hook_key cannot be empty")


@dataclass(frozen=True, slots=True)
class ManifestContributions:
    """Container for all contributions declared in a manifest."""

    slots: tuple[SlotContribution, ...] = ()
    hooks: tuple[HookContribution, ...] = ()


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Declarative metadata describing a plugin."""

    manifest_version: str
    plugin_id: str
    plugin_version: SemVer
    requires_switchboard: ApiRange
    entrypoint: str
    name: str = ""
    description: str = ""
    contributions: ManifestContributions = field(default_factory=ManifestContributions)
    requires: tuple[str, ...] = ()  # Plugin IDs this depends on (hard dependencies)
    optional_requires: tuple[str, ...] = ()  # Plugin IDs for ordering only (soft dependencies)

    def __post_init__(self) -> None:
        if not self.manifest_version:
            raise ValueError("manifest_version is required")
        if not self.plugin_id:
            raise ValueError("plugin_id is required")
        if not self.entrypoint:
            raise ValueError("entrypoint is required")


# =============================================================================
# Introspection Types (V2)
# =============================================================================


@dataclass(frozen=True, slots=True)
class RuntimeInfo:
    """Summary information about the Switchboard runtime.

    This provides a quick overview of the framework state without
    full snapshot details. Useful for health checks and dashboards.
    """

    framework_version: str
    python_version: str
    plugin_count: int
    active_plugin_count: int
    slot_count: int
    hook_count: int


@dataclass(frozen=True, slots=True)
class ContributionSnapshot:
    """Snapshot of a contribution for introspection.

    Used within SlotSnapshot and HookSnapshot to show what's
    contributing and in what order.
    """

    contribution_id: str
    plugin_id: str
    priority: int


@dataclass(frozen=True, slots=True)
class PluginSnapshot:
    """Snapshot of a plugin's state.

    Captures plugin identity, version, lifecycle state, and
    the IDs of its contributions.
    """

    plugin_id: str
    version: str
    state: str  # Matches PluginLifecycle: ready, starting, active, stopping, failed
    contributions: tuple[str, ...]  # contribution IDs


@dataclass(frozen=True, slots=True)
class SlotSnapshot:
    """Snapshot of a slot and its contributions.

    Shows what's wired into this slot, in resolution order.
    """

    slot_key: str
    policy: str
    contributions: tuple[ContributionSnapshot, ...]


@dataclass(frozen=True, slots=True)
class HookSnapshot:
    """Snapshot of a hook and its handlers.

    Shows what handlers are registered, in execution order.
    """

    hook_key: str
    kind: str
    policy: str
    handlers: tuple[ContributionSnapshot, ...]


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Complete snapshot of the Switchboard runtime state.

    This captures the full state at a point in time for debugging,
    logging, and introspection. The timestamp is timezone-aware (UTC).
    """

    timestamp: datetime
    runtime: RuntimeInfo
    plugins: tuple[PluginSnapshot, ...]
    slots: tuple[SlotSnapshot, ...]
    hooks: tuple[HookSnapshot, ...]


@dataclass(frozen=True, slots=True)
class ActivationPlan:
    """Plan for activating plugins in dependency order.

    Produced by activation_plan() and returned by activate_all().
    """

    order: tuple[str, ...]  # Plugin IDs in activation order
    blocked: dict[str, str]  # plugin_id -> reason (missing dep, cycle, etc.)
    cycles: tuple[tuple[str, ...], ...]  # Detected cycles (if any)
