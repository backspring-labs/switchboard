// Domain models
export {
  SemVer,
  ApiRange,
  SlotPolicy,
  HookKind,
  HookPolicy,
  SlotDefinition,
  HookDefinition,
  Contribution,
  SlotContribution,
  HookContribution,
  ManifestContributions,
  PluginManifest,
} from "./domain/models.js";

export type {
  ContributionParams,
  SlotContributionParams,
  HookContributionParams,
  PluginManifestParams,
  RuntimeInfo,
  ContributionSnapshot,
  PluginSnapshot,
  SlotSnapshot,
  HookSnapshot,
  RuntimeSnapshot,
  ActivationPlan,
} from "./domain/models.js";

// Domain errors
export {
  SwitchboardError,
  PluginNotFoundError,
  SlotNotFoundError,
  HookNotFoundError,
  CompatibilityError,
  LifecycleError,
  DuplicateRegistrationError,
  ManifestError,
  ContributionError,
} from "./domain/errors.js";

// Domain lifecycle
export { PluginState, PluginLifecycle } from "./domain/lifecycle.js";

// Domain core
export { PatchPanel } from "./domain/patch-panel.js";

// Ports
export type { HookRouterPort, LoaderPort } from "./domain/ports.js";

// Application
export { parseManifest } from "./application/manifest.js";

// Adapters
export { MemoryHookRouter } from "./adapters/memory-hook-router.js";
export { RegistryLoader } from "./adapters/registry-loader.js";

export { VERSION } from "./version.js";
