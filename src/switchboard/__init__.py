"""Switchboard: A Python-first plugin runtime for host-owned extensibility."""

from switchboard.application.manifest import load_manifest, parse_manifest
from switchboard.domain.errors import (
    CompatibilityError,
    ContributionError,
    DuplicateRegistrationError,
    HookNotFoundError,
    LifecycleError,
    ManifestError,
    PluginNotFoundError,
    SlotNotFoundError,
    SwitchboardError,
)
from switchboard.domain.models import (
    ActivationPlan,
    ApiRange,
    Contribution,
    ContributionSnapshot,
    HookContribution,
    HookDefinition,
    HookKind,
    HookPolicy,
    HookSnapshot,
    ManifestContributions,
    PluginManifest,
    PluginSnapshot,
    RuntimeInfo,
    RuntimeSnapshot,
    SemVer,
    SlotContribution,
    SlotDefinition,
    SlotPolicy,
    SlotSnapshot,
)
from switchboard.domain.patch_panel import PatchPanel

__version__ = "0.2.0"

__all__ = [
    # Sorted alphabetically per ruff RUF022
    "ActivationPlan",
    "ApiRange",
    "CompatibilityError",
    "Contribution",
    "ContributionError",
    "ContributionSnapshot",
    "DuplicateRegistrationError",
    "HookContribution",
    "HookDefinition",
    "HookKind",
    "HookNotFoundError",
    "HookPolicy",
    "HookSnapshot",
    "LifecycleError",
    "ManifestContributions",
    "ManifestError",
    "PatchPanel",
    "PluginManifest",
    "PluginNotFoundError",
    "PluginSnapshot",
    "RuntimeInfo",
    "RuntimeSnapshot",
    "SemVer",
    "SlotContribution",
    "SlotDefinition",
    "SlotNotFoundError",
    "SlotPolicy",
    "SlotSnapshot",
    "SwitchboardError",
    "__version__",
    "load_manifest",
    "parse_manifest",
]
