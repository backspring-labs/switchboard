import { ManifestError } from "../domain/errors.js";
import {
  ApiRange,
  HookContribution,
  ManifestContributions,
  PluginManifest,
  SemVer,
  SlotContribution,
} from "../domain/models.js";

export function parseManifest(data: Record<string, unknown>): PluginManifest {
  // Required fields
  const manifestVersion = requireField(data, "manifest_version", "string");
  const pluginId = requireField(data, "plugin_id", "string");
  const pluginVersionStr = requireField(data, "plugin_version", "string");
  const requiresSwitchboardStr = requireField(
    data,
    "requires_switchboard",
    "string",
  );
  const entrypoint = requireField(data, "entrypoint", "string");

  // Parse version and range
  let pluginVersion: SemVer;
  try {
    pluginVersion = SemVer.parse(pluginVersionStr);
  } catch (e) {
    throw new ManifestError(
      `Invalid plugin_version: ${e instanceof Error ? e.message : String(e)}`,
    );
  }

  let requiresSwitchboard: ApiRange;
  try {
    requiresSwitchboard = ApiRange.parse(requiresSwitchboardStr);
  } catch (e) {
    throw new ManifestError(
      `Invalid requires_switchboard: ${e instanceof Error ? e.message : String(e)}`,
    );
  }

  // Optional fields
  const name =
    typeof data.name === "string" ? data.name : "";
  const description =
    typeof data.description === "string" ? data.description : "";

  // Parse contributions
  const contributions = parseContributions(
    data.contributions as Record<string, unknown> | undefined,
    pluginId,
  );

  // Parse dependency declarations
  const requires = parseStringList(
    data.requires as unknown[] | undefined,
    "requires",
  );
  const optionalRequires = parseStringList(
    data.optional_requires as unknown[] | undefined,
    "optional_requires",
  );

  return new PluginManifest({
    manifestVersion,
    pluginId,
    pluginVersion,
    requiresSwitchboard,
    entrypoint,
    name,
    description,
    contributions,
    requires,
    optionalRequires,
  });
}

function requireField(
  data: Record<string, unknown>,
  field: string,
  expectedType: string,
): string {
  if (!(field in data)) {
    throw new ManifestError(`Missing required field: ${field}`);
  }

  const value = data[field];
  if (typeof value !== expectedType) {
    throw new ManifestError(
      `Field '${field}' must be ${expectedType}, got ${typeof value}`,
    );
  }

  return value as string;
}

function parseStringList(
  data: unknown[] | undefined,
  fieldName: string,
): string[] {
  if (data === undefined || data === null) {
    return [];
  }

  if (!Array.isArray(data)) {
    throw new ManifestError(`${fieldName} must be a list`);
  }

  for (let i = 0; i < data.length; i++) {
    if (typeof data[i] !== "string") {
      throw new ManifestError(
        `${fieldName}[${i}] must be a string, got ${typeof data[i]}`,
      );
    }
  }

  return data as string[];
}

function parseContributions(
  data: Record<string, unknown> | undefined,
  pluginId: string,
): ManifestContributions {
  if (!data) {
    return new ManifestContributions();
  }

  if (typeof data !== "object" || Array.isArray(data)) {
    throw new ManifestError("contributions must be a mapping");
  }

  const slots = parseSlotContributions(
    data.slots as unknown[] | undefined,
    pluginId,
  );
  const hooks = parseHookContributions(
    data.hooks as unknown[] | undefined,
    pluginId,
  );

  return new ManifestContributions({ slots, hooks });
}

function parseSlotContributions(
  data: unknown[] | undefined,
  pluginId: string,
): SlotContribution[] {
  if (!data) return [];

  if (!Array.isArray(data)) {
    throw new ManifestError("contributions.slots must be a list");
  }

  return data.map((item, i) => {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      throw new ManifestError(`contributions.slots[${i}] must be a mapping`);
    }

    const record = item as Record<string, unknown>;

    try {
      return new SlotContribution({
        pluginId,
        contributionId: requireField(record, "contribution_id", "string"),
        slotKey: requireField(record, "slot_key", "string"),
        priority:
          typeof record.priority === "number" ? record.priority : 50,
        factory:
          typeof record.factory === "string" ? record.factory : "",
        metadata:
          typeof record.metadata === "object" && record.metadata !== null
            ? (record.metadata as Record<string, unknown>)
            : undefined,
      });
    } catch (e) {
      if (e instanceof ManifestError) throw e;
      throw new ManifestError(
        `Invalid slot contribution [${i}]: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  });
}

function parseHookContributions(
  data: unknown[] | undefined,
  pluginId: string,
): HookContribution[] {
  if (!data) return [];

  if (!Array.isArray(data)) {
    throw new ManifestError("contributions.hooks must be a list");
  }

  return data.map((item, i) => {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      throw new ManifestError(`contributions.hooks[${i}] must be a mapping`);
    }

    const record = item as Record<string, unknown>;

    try {
      return new HookContribution({
        pluginId,
        contributionId: requireField(record, "contribution_id", "string"),
        hookKey: requireField(record, "hook_key", "string"),
        priority:
          typeof record.priority === "number" ? record.priority : 50,
        handler:
          typeof record.handler === "string" ? record.handler : "",
        metadata:
          typeof record.metadata === "object" && record.metadata !== null
            ? (record.metadata as Record<string, unknown>)
            : undefined,
      });
    } catch (e) {
      if (e instanceof ManifestError) throw e;
      throw new ManifestError(
        `Invalid hook contribution [${i}]: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  });
}
