// =============================================================================
// Value Objects
// =============================================================================

const SEMVER_PATTERN = /^(\d+)\.(\d+)\.(\d+)$/;

export class SemVer {
  readonly major: number;
  readonly minor: number;
  readonly patch: number;

  constructor(major: number, minor: number, patch: number) {
    this.major = major;
    this.minor = minor;
    this.patch = patch;
    Object.freeze(this);
  }

  static parse(versionStr: string): SemVer {
    const match = versionStr.trim().match(SEMVER_PATTERN);
    if (!match) {
      throw new Error(
        `Invalid version format: '${versionStr}' (expected X.Y.Z)`,
      );
    }
    return new SemVer(
      parseInt(match[1]!, 10),
      parseInt(match[2]!, 10),
      parseInt(match[3]!, 10),
    );
  }

  toString(): string {
    return `${this.major}.${this.minor}.${this.patch}`;
  }

  private tuple(): [number, number, number] {
    return [this.major, this.minor, this.patch];
  }

  eq(other: SemVer): boolean {
    return (
      this.major === other.major &&
      this.minor === other.minor &&
      this.patch === other.patch
    );
  }

  lt(other: SemVer): boolean {
    const a = this.tuple();
    const b = other.tuple();
    for (let i = 0; i < 3; i++) {
      if (a[i]! < b[i]!) return true;
      if (a[i]! > b[i]!) return false;
    }
    return false;
  }

  le(other: SemVer): boolean {
    return this.lt(other) || this.eq(other);
  }

  gt(other: SemVer): boolean {
    return other.lt(this);
  }

  ge(other: SemVer): boolean {
    return other.le(this);
  }
}

const CONSTRAINT_PATTERN = /(>=|<=|>|<|==)\s*(\d+\.\d+\.\d+)/;

export class ApiRange {
  readonly constraints: readonly [string, SemVer][];

  constructor(constraints: [string, SemVer][]) {
    this.constraints = Object.freeze(constraints.map((c) => Object.freeze(c) as [string, SemVer]));
    Object.freeze(this);
  }

  static parse(rangeStr: string): ApiRange {
    const constraints: [string, SemVer][] = [];
    for (const part of rangeStr.split(",")) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      const match = trimmed.match(CONSTRAINT_PATTERN);
      if (!match) {
        throw new Error(`Invalid constraint format: '${trimmed}'`);
      }
      constraints.push([match[1]!, SemVer.parse(match[2]!)]);
    }
    if (constraints.length === 0) {
      throw new Error(`Empty version range: '${rangeStr}'`);
    }
    return new ApiRange(constraints);
  }

  contains(version: SemVer): boolean {
    const ops: Record<string, (v: SemVer, c: SemVer) => boolean> = {
      ">=": (v, c) => v.ge(c),
      "<=": (v, c) => v.le(c),
      ">": (v, c) => v.gt(c),
      "<": (v, c) => v.lt(c),
      "==": (v, c) => v.eq(c),
    };
    for (const [op, constraintVersion] of this.constraints) {
      const fn = ops[op];
      if (!fn || !fn(version, constraintVersion)) {
        return false;
      }
    }
    return true;
  }

  toString(): string {
    return this.constraints.map(([op, v]) => `${op}${v}`).join(",");
  }
}

// =============================================================================
// Enums
// =============================================================================

export const SlotPolicy = {
  MULTI: "multi",
  SINGLE: "single",
} as const;
export type SlotPolicy = (typeof SlotPolicy)[keyof typeof SlotPolicy];

export const HookKind = {
  EVENT: "event",
  COMMAND: "command",
  LIFECYCLE: "lifecycle",
} as const;
export type HookKind = (typeof HookKind)[keyof typeof HookKind];

export const HookPolicy = {
  BROADCAST: "broadcast",
  FIRST_RESULT: "first_result",
} as const;
export type HookPolicy = (typeof HookPolicy)[keyof typeof HookPolicy];

// =============================================================================
// Entities
// =============================================================================

export class SlotDefinition {
  readonly slotKey: string;
  readonly policy: SlotPolicy;
  readonly description: string;

  constructor(
    slotKey: string,
    options?: { policy?: SlotPolicy; description?: string },
  ) {
    if (!slotKey) {
      throw new Error("slot_key cannot be empty");
    }
    this.slotKey = slotKey;
    this.policy = options?.policy ?? SlotPolicy.MULTI;
    this.description = options?.description ?? "";
    Object.freeze(this);
  }
}

export class HookDefinition {
  readonly hookKey: string;
  readonly kind: HookKind;
  readonly policy: HookPolicy | undefined;
  readonly description: string;

  constructor(
    hookKey: string,
    options?: {
      kind?: HookKind;
      policy?: HookPolicy;
      description?: string;
    },
  ) {
    if (!hookKey) {
      throw new Error("hook_key cannot be empty");
    }
    this.hookKey = hookKey;
    this.kind = options?.kind ?? HookKind.EVENT;
    this.policy = options?.policy;
    this.description = options?.description ?? "";
    Object.freeze(this);
  }

  get effectivePolicy(): HookPolicy {
    if (this.policy !== undefined) {
      return this.policy;
    }
    if (this.kind === HookKind.COMMAND) {
      return HookPolicy.FIRST_RESULT;
    }
    return HookPolicy.BROADCAST;
  }
}

export interface ContributionParams {
  pluginId: string;
  contributionId: string;
  priority?: number;
  metadata?: Record<string, unknown>;
}

export class Contribution {
  readonly pluginId: string;
  readonly contributionId: string;
  readonly priority: number;
  readonly metadata: Record<string, unknown>;

  constructor(params: ContributionParams) {
    if (!params.pluginId) {
      throw new Error("plugin_id cannot be empty");
    }
    if (!params.contributionId) {
      throw new Error("contribution_id cannot be empty");
    }
    this.pluginId = params.pluginId;
    this.contributionId = params.contributionId;
    this.priority = params.priority ?? 50;
    this.metadata = Object.freeze({ ...params.metadata }) as Record<
      string,
      unknown
    >;
  }
}

export interface SlotContributionParams extends ContributionParams {
  slotKey: string;
  factory?: string;
}

export class SlotContribution extends Contribution {
  readonly slotKey: string;
  readonly factory: string;

  constructor(params: SlotContributionParams) {
    super(params);
    if (!params.slotKey) {
      throw new Error("slot_key cannot be empty");
    }
    this.slotKey = params.slotKey;
    this.factory = params.factory ?? "";
    Object.freeze(this);
  }
}

export interface HookContributionParams extends ContributionParams {
  hookKey: string;
  handler?: string;
}

export class HookContribution extends Contribution {
  readonly hookKey: string;
  readonly handler: string;

  constructor(params: HookContributionParams) {
    super(params);
    if (!params.hookKey) {
      throw new Error("hook_key cannot be empty");
    }
    this.hookKey = params.hookKey;
    this.handler = params.handler ?? "";
    Object.freeze(this);
  }
}

export class ManifestContributions {
  readonly slots: readonly SlotContribution[];
  readonly hooks: readonly HookContribution[];

  constructor(
    options?: {
      slots?: SlotContribution[];
      hooks?: HookContribution[];
    },
  ) {
    this.slots = Object.freeze([...(options?.slots ?? [])]);
    this.hooks = Object.freeze([...(options?.hooks ?? [])]);
    Object.freeze(this);
  }
}

export interface PluginManifestParams {
  manifestVersion: string;
  pluginId: string;
  pluginVersion: SemVer;
  requiresSwitchboard: ApiRange;
  entrypoint: string;
  name?: string;
  description?: string;
  contributions?: ManifestContributions;
  requires?: string[];
  optionalRequires?: string[];
}

export class PluginManifest {
  readonly manifestVersion: string;
  readonly pluginId: string;
  readonly pluginVersion: SemVer;
  readonly requiresSwitchboard: ApiRange;
  readonly entrypoint: string;
  readonly name: string;
  readonly description: string;
  readonly contributions: ManifestContributions;
  readonly requires: readonly string[];
  readonly optionalRequires: readonly string[];

  constructor(params: PluginManifestParams) {
    if (!params.manifestVersion) {
      throw new Error("manifest_version is required");
    }
    if (!params.pluginId) {
      throw new Error("plugin_id is required");
    }
    if (!params.entrypoint) {
      throw new Error("entrypoint is required");
    }
    this.manifestVersion = params.manifestVersion;
    this.pluginId = params.pluginId;
    this.pluginVersion = params.pluginVersion;
    this.requiresSwitchboard = params.requiresSwitchboard;
    this.entrypoint = params.entrypoint;
    this.name = params.name ?? "";
    this.description = params.description ?? "";
    this.contributions = params.contributions ?? new ManifestContributions();
    this.requires = Object.freeze([...(params.requires ?? [])]);
    this.optionalRequires = Object.freeze([
      ...(params.optionalRequires ?? []),
    ]);
    Object.freeze(this);
  }
}

// =============================================================================
// Introspection Types (V2)
// =============================================================================

export interface RuntimeInfo {
  readonly frameworkVersion: string;
  readonly platformVersion: string;
  readonly pluginCount: number;
  readonly activePluginCount: number;
  readonly slotCount: number;
  readonly hookCount: number;
}

export interface ContributionSnapshot {
  readonly contributionId: string;
  readonly pluginId: string;
  readonly priority: number;
}

export interface PluginSnapshot {
  readonly pluginId: string;
  readonly version: string;
  readonly state: string;
  readonly contributions: readonly string[];
}

export interface SlotSnapshot {
  readonly slotKey: string;
  readonly policy: string;
  readonly contributions: readonly ContributionSnapshot[];
}

export interface HookSnapshot {
  readonly hookKey: string;
  readonly kind: string;
  readonly policy: string;
  readonly handlers: readonly ContributionSnapshot[];
}

export interface RuntimeSnapshot {
  readonly timestamp: string;
  readonly runtime: RuntimeInfo;
  readonly plugins: readonly PluginSnapshot[];
  readonly slots: readonly SlotSnapshot[];
  readonly hooks: readonly HookSnapshot[];
}

export interface ActivationPlan {
  readonly order: readonly string[];
  readonly blocked: Readonly<Record<string, string>>;
  readonly cycles: readonly (readonly string[])[];
}
