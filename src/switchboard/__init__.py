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
    ApiRange,
    Contribution,
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
from switchboard.domain.patch_panel import PatchPanel

__version__ = "0.1.0"

__all__ = [
    # Sorted alphabetically per ruff RUF022
    "ApiRange",
    "CompatibilityError",
    "Contribution",
    "ContributionError",
    "DuplicateRegistrationError",
    "HookContribution",
    "HookDefinition",
    "HookKind",
    "HookNotFoundError",
    "HookPolicy",
    "LifecycleError",
    "ManifestContributions",
    "ManifestError",
    "PatchPanel",
    "PluginManifest",
    "PluginNotFoundError",
    "SemVer",
    "SlotContribution",
    "SlotDefinition",
    "SlotNotFoundError",
    "SlotPolicy",
    "SwitchboardError",
    "__version__",
    "load_manifest",
    "parse_manifest",
]
