import { describe, it, expect } from "vitest";
import { ManifestError } from "../../src/domain/errors.js";
import { SlotContribution, HookContribution } from "../../src/domain/models.js";
import { parseManifest } from "../../src/application/manifest.js";

const MINIMAL_DATA = {
  manifest_version: "1",
  plugin_id: "com.example.test",
  plugin_version: "1.0.0",
  requires_switchboard: ">=0.1.0,<1.0.0",
  entrypoint: "my_plugin:MyPlugin",
};

describe("parseManifest", () => {
  it("parses minimal manifest", () => {
    const manifest = parseManifest(MINIMAL_DATA);

    expect(manifest.manifestVersion).toBe("1");
    expect(manifest.pluginId).toBe("com.example.test");
    expect(manifest.pluginVersion.toString()).toBe("1.0.0");
    expect(manifest.entrypoint).toBe("my_plugin:MyPlugin");
    expect(manifest.name).toBe("");
    expect(manifest.description).toBe("");
    expect(manifest.contributions.slots).toEqual([]);
    expect(manifest.contributions.hooks).toEqual([]);
  });

  it("parses full manifest", () => {
    const data = {
      manifest_version: "1",
      plugin_id: "com.example.full",
      plugin_version: "2.1.0",
      requires_switchboard: ">=0.1.0",
      entrypoint: "full_plugin:FullPlugin",
      name: "Full Plugin",
      description: "A plugin with all fields",
      contributions: {
        slots: [
          {
            contribution_id: "sidebar.widget",
            slot_key: "ui.sidebar",
            priority: 75,
            factory: "full_plugin:SidebarWidget",
            metadata: { icon: "star" },
          },
        ],
        hooks: [
          {
            contribution_id: "on.started",
            hook_key: "app.started",
            priority: 100,
            handler: "full_plugin:on_started",
          },
        ],
      },
    };

    const manifest = parseManifest(data);

    expect(manifest.pluginId).toBe("com.example.full");
    expect(manifest.name).toBe("Full Plugin");
    expect(manifest.description).toBe("A plugin with all fields");

    expect(manifest.contributions.slots.length).toBe(1);
    const slot = manifest.contributions.slots[0]!;
    expect(slot).toBeInstanceOf(SlotContribution);
    expect(slot.pluginId).toBe("com.example.full");
    expect(slot.contributionId).toBe("sidebar.widget");
    expect(slot.slotKey).toBe("ui.sidebar");
    expect(slot.priority).toBe(75);
    expect(slot.factory).toBe("full_plugin:SidebarWidget");

    expect(manifest.contributions.hooks.length).toBe(1);
    const hook = manifest.contributions.hooks[0]!;
    expect(hook).toBeInstanceOf(HookContribution);
    expect(hook.pluginId).toBe("com.example.full");
    expect(hook.contributionId).toBe("on.started");
    expect(hook.hookKey).toBe("app.started");
    expect(hook.priority).toBe(100);
    expect(hook.handler).toBe("full_plugin:on_started");
  });

  it("parses multiple contributions", () => {
    const data = {
      ...MINIMAL_DATA,
      plugin_id: "com.example.multi",
      contributions: {
        slots: [
          { contribution_id: "slot1", slot_key: "ui.sidebar" },
          { contribution_id: "slot2", slot_key: "ui.toolbar" },
        ],
        hooks: [
          { contribution_id: "hook1", hook_key: "app.started" },
          { contribution_id: "hook2", hook_key: "app.stopped" },
        ],
      },
    };

    const manifest = parseManifest(data);
    expect(manifest.contributions.slots.length).toBe(2);
    expect(manifest.contributions.hooks.length).toBe(2);
  });

  it("defaults priority to 50", () => {
    const data = {
      ...MINIMAL_DATA,
      contributions: {
        slots: [{ contribution_id: "c1", slot_key: "ui.sidebar" }],
        hooks: [{ contribution_id: "h1", hook_key: "app.started" }],
      },
    };

    const manifest = parseManifest(data);
    expect(manifest.contributions.slots[0]!.priority).toBe(50);
    expect(manifest.contributions.hooks[0]!.priority).toBe(50);
  });
});

describe("parseManifest errors", () => {
  it("rejects missing manifest_version", () => {
    const { manifest_version: _, ...data } = MINIMAL_DATA;
    expect(() => parseManifest(data)).toThrow(ManifestError);
    expect(() => parseManifest(data)).toThrow(
      "Missing required field: manifest_version",
    );
  });

  it("rejects missing plugin_id", () => {
    const { plugin_id: _, ...data } = MINIMAL_DATA;
    expect(() => parseManifest(data)).toThrow("Missing required field: plugin_id");
  });

  it("rejects invalid plugin_version", () => {
    const data = { ...MINIMAL_DATA, plugin_version: "not.a.version" };
    expect(() => parseManifest(data)).toThrow("Invalid plugin_version");
  });

  it("rejects invalid requires_switchboard", () => {
    const data = { ...MINIMAL_DATA, requires_switchboard: "invalid range" };
    expect(() => parseManifest(data)).toThrow("Invalid requires_switchboard");
  });

  it("rejects wrong type for required field", () => {
    const data = { ...MINIMAL_DATA, manifest_version: 1 };
    expect(() => parseManifest(data)).toThrow("must be string");
  });

  it("rejects contributions not a mapping", () => {
    const data = { ...MINIMAL_DATA, contributions: "not a mapping" };
    expect(() => parseManifest(data)).toThrow(
      "contributions must be a mapping",
    );
  });

  it("rejects slots not a list", () => {
    const data = {
      ...MINIMAL_DATA,
      contributions: { slots: "not a list" },
    };
    expect(() => parseManifest(data)).toThrow(
      "contributions.slots must be a list",
    );
  });

  it("rejects slot missing contribution_id", () => {
    const data = {
      ...MINIMAL_DATA,
      contributions: { slots: [{ slot_key: "ui.sidebar" }] },
    };
    expect(() => parseManifest(data)).toThrow(
      "Missing required field: contribution_id",
    );
  });

  it("rejects hook missing hook_key", () => {
    const data = {
      ...MINIMAL_DATA,
      contributions: { hooks: [{ contribution_id: "h1" }] },
    };
    expect(() => parseManifest(data)).toThrow(
      "Missing required field: hook_key",
    );
  });
});

describe("unknown fields", () => {
  it("ignores unknown top-level fields", () => {
    const data = {
      ...MINIMAL_DATA,
      future_field: "some value",
      another_unknown: 123,
    };
    const manifest = parseManifest(data);
    expect(manifest.pluginId).toBe("com.example.test");
  });

  it("ignores unknown contribution fields", () => {
    const data = {
      ...MINIMAL_DATA,
      contributions: {
        slots: [
          {
            contribution_id: "c1",
            slot_key: "ui.sidebar",
            future_field: "ignored",
          },
        ],
      },
    };
    const manifest = parseManifest(data);
    expect(manifest.contributions.slots.length).toBe(1);
  });
});

describe("dependency fields", () => {
  it("defaults requires to empty", () => {
    const manifest = parseManifest(MINIMAL_DATA);
    expect(manifest.requires).toEqual([]);
    expect(manifest.optionalRequires).toEqual([]);
  });

  it("parses requires list", () => {
    const data = {
      ...MINIMAL_DATA,
      requires: ["com.example.core", "com.example.logging"],
    };
    const manifest = parseManifest(data);
    expect([...manifest.requires]).toEqual([
      "com.example.core",
      "com.example.logging",
    ]);
  });

  it("parses optional_requires list", () => {
    const data = {
      ...MINIMAL_DATA,
      optional_requires: ["com.example.analytics", "com.example.telemetry"],
    };
    const manifest = parseManifest(data);
    expect([...manifest.optionalRequires]).toEqual([
      "com.example.analytics",
      "com.example.telemetry",
    ]);
  });

  it("parses both requires and optional_requires", () => {
    const data = {
      ...MINIMAL_DATA,
      requires: ["com.example.core"],
      optional_requires: ["com.example.analytics"],
    };
    const manifest = parseManifest(data);
    expect([...manifest.requires]).toEqual(["com.example.core"]);
    expect([...manifest.optionalRequires]).toEqual(["com.example.analytics"]);
  });

  it("rejects requires not a list", () => {
    const data = { ...MINIMAL_DATA, requires: "not a list" };
    expect(() => parseManifest(data)).toThrow("requires must be a list");
  });

  it("rejects requires item not string", () => {
    const data = { ...MINIMAL_DATA, requires: [123] };
    expect(() => parseManifest(data)).toThrow("requires[0] must be a string");
  });

  it("rejects optional_requires not a list", () => {
    const data = { ...MINIMAL_DATA, optional_requires: "not a list" };
    expect(() => parseManifest(data)).toThrow(
      "optional_requires must be a list",
    );
  });

  it("parses empty requires list", () => {
    const data = { ...MINIMAL_DATA, requires: [] };
    const manifest = parseManifest(data);
    expect(manifest.requires).toEqual([]);
  });
});
