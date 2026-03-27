import { describe, it, expect } from "vitest";
import {
  SemVer,
  ApiRange,
  SlotDefinition,
  SlotPolicy,
  HookDefinition,
  HookKind,
  HookPolicy,
  SlotContribution,
  HookContribution,
  ManifestContributions,
  PluginManifest,
} from "../../src/domain/models.js";

describe("SemVer", () => {
  it("parses valid version", () => {
    const v = SemVer.parse("1.2.3");
    expect(v.major).toBe(1);
    expect(v.minor).toBe(2);
    expect(v.patch).toBe(3);
  });

  it("parses with whitespace", () => {
    const v = SemVer.parse("  1.2.3  ");
    expect(v.eq(new SemVer(1, 2, 3))).toBe(true);
  });

  it("rejects invalid format", () => {
    expect(() => SemVer.parse("1.2")).toThrow("Invalid version format");
  });

  it("rejects non-numeric", () => {
    expect(() => SemVer.parse("1.2.x")).toThrow("Invalid version format");
  });

  it("converts to string", () => {
    expect(new SemVer(1, 2, 3).toString()).toBe("1.2.3");
  });

  it("compares lt", () => {
    expect(new SemVer(1, 0, 0).lt(new SemVer(2, 0, 0))).toBe(true);
    expect(new SemVer(1, 0, 0).lt(new SemVer(1, 1, 0))).toBe(true);
    expect(new SemVer(1, 0, 0).lt(new SemVer(1, 0, 1))).toBe(true);
  });

  it("compares le", () => {
    expect(new SemVer(1, 0, 0).le(new SemVer(1, 0, 0))).toBe(true);
    expect(new SemVer(1, 0, 0).le(new SemVer(2, 0, 0))).toBe(true);
  });

  it("compares gt", () => {
    expect(new SemVer(2, 0, 0).gt(new SemVer(1, 0, 0))).toBe(true);
    expect(new SemVer(1, 1, 0).gt(new SemVer(1, 0, 0))).toBe(true);
  });

  it("compares ge", () => {
    expect(new SemVer(1, 0, 0).ge(new SemVer(1, 0, 0))).toBe(true);
    expect(new SemVer(2, 0, 0).ge(new SemVer(1, 0, 0))).toBe(true);
  });

  it("checks equality", () => {
    expect(new SemVer(1, 2, 3).eq(new SemVer(1, 2, 3))).toBe(true);
    expect(new SemVer(1, 2, 3).eq(new SemVer(1, 2, 4))).toBe(false);
  });

  it("is frozen", () => {
    const v = new SemVer(1, 2, 3);
    expect(() => {
      (v as Record<string, unknown>).major = 2;
    }).toThrow();
  });
});

describe("ApiRange", () => {
  it("parses single constraint", () => {
    const r = ApiRange.parse(">=1.0.0");
    expect(r.constraints.length).toBe(1);
    expect(r.constraints[0]![0]).toBe(">=");
    expect(r.constraints[0]![1].eq(new SemVer(1, 0, 0))).toBe(true);
  });

  it("parses multiple constraints", () => {
    const r = ApiRange.parse(">=1.0.0,<2.0.0");
    expect(r.constraints.length).toBe(2);
    expect(r.constraints[0]![0]).toBe(">=");
    expect(r.constraints[1]![0]).toBe("<");
  });

  it("parses with whitespace", () => {
    const r = ApiRange.parse(">= 1.0.0 , < 2.0.0");
    expect(r.contains(new SemVer(1, 5, 0))).toBe(true);
  });

  it("rejects empty range", () => {
    expect(() => ApiRange.parse("")).toThrow("Empty version range");
  });

  it("rejects invalid constraint", () => {
    expect(() => ApiRange.parse("~1.0.0")).toThrow("Invalid constraint");
  });

  it("contains gte", () => {
    const r = ApiRange.parse(">=1.0.0");
    expect(r.contains(new SemVer(1, 0, 0))).toBe(true);
    expect(r.contains(new SemVer(2, 0, 0))).toBe(true);
    expect(r.contains(new SemVer(0, 9, 0))).toBe(false);
  });

  it("contains lt", () => {
    const r = ApiRange.parse("<2.0.0");
    expect(r.contains(new SemVer(1, 9, 9))).toBe(true);
    expect(r.contains(new SemVer(2, 0, 0))).toBe(false);
  });

  it("contains range", () => {
    const r = ApiRange.parse(">=0.1.0,<1.0.0");
    expect(r.contains(new SemVer(0, 1, 0))).toBe(true);
    expect(r.contains(new SemVer(0, 5, 0))).toBe(true);
    expect(r.contains(new SemVer(0, 0, 9))).toBe(false);
    expect(r.contains(new SemVer(1, 0, 0))).toBe(false);
  });

  it("contains exact", () => {
    const r = ApiRange.parse("==1.2.3");
    expect(r.contains(new SemVer(1, 2, 3))).toBe(true);
    expect(r.contains(new SemVer(1, 2, 4))).toBe(false);
  });

  it("converts to string", () => {
    const r = ApiRange.parse(">=1.0.0,<2.0.0");
    expect(r.toString()).toBe(">=1.0.0,<2.0.0");
  });
});

describe("SlotDefinition", () => {
  it("creates with defaults", () => {
    const slot = new SlotDefinition("ui.sidebar");
    expect(slot.slotKey).toBe("ui.sidebar");
    expect(slot.policy).toBe(SlotPolicy.MULTI);
    expect(slot.description).toBe("");
  });

  it("creates with single policy", () => {
    const slot = new SlotDefinition("ui.main", { policy: SlotPolicy.SINGLE });
    expect(slot.policy).toBe(SlotPolicy.SINGLE);
  });

  it("rejects empty key", () => {
    expect(() => new SlotDefinition("")).toThrow("slot_key cannot be empty");
  });
});

describe("HookDefinition", () => {
  it("creates with defaults", () => {
    const hook = new HookDefinition("app.started");
    expect(hook.hookKey).toBe("app.started");
    expect(hook.kind).toBe(HookKind.EVENT);
    expect(hook.policy).toBeUndefined();
  });

  it("derives effective policy from kind", () => {
    const eventHook = new HookDefinition("event.foo", {
      kind: HookKind.EVENT,
    });
    expect(eventHook.effectivePolicy).toBe(HookPolicy.BROADCAST);

    const commandHook = new HookDefinition("cmd.foo", {
      kind: HookKind.COMMAND,
    });
    expect(commandHook.effectivePolicy).toBe(HookPolicy.FIRST_RESULT);

    const lifecycleHook = new HookDefinition("life.foo", {
      kind: HookKind.LIFECYCLE,
    });
    expect(lifecycleHook.effectivePolicy).toBe(HookPolicy.BROADCAST);
  });

  it("uses explicit policy override", () => {
    const hook = new HookDefinition("cmd.foo", {
      kind: HookKind.COMMAND,
      policy: HookPolicy.BROADCAST,
    });
    expect(hook.effectivePolicy).toBe(HookPolicy.BROADCAST);
  });

  it("rejects empty key", () => {
    expect(() => new HookDefinition("")).toThrow("hook_key cannot be empty");
  });
});

describe("SlotContribution", () => {
  it("creates with minimal params", () => {
    const contrib = new SlotContribution({
      pluginId: "com.example.plugin",
      contributionId: "my.contrib",
      slotKey: "ui.sidebar",
    });
    expect(contrib.priority).toBe(50);
    expect(contrib.factory).toBe("");
    expect(contrib.metadata).toEqual({});
  });

  it("creates with full params", () => {
    const contrib = new SlotContribution({
      pluginId: "com.example.plugin",
      contributionId: "my.contrib",
      slotKey: "ui.sidebar",
      priority: 100,
      factory: "my_plugin:build_widget",
      metadata: { icon: "star" },
    });
    expect(contrib.priority).toBe(100);
    expect(contrib.factory).toBe("my_plugin:build_widget");
  });

  it("rejects empty plugin_id", () => {
    expect(
      () =>
        new SlotContribution({
          pluginId: "",
          contributionId: "x",
          slotKey: "y",
        }),
    ).toThrow();
  });
});

describe("HookContribution", () => {
  it("creates with minimal params", () => {
    const contrib = new HookContribution({
      pluginId: "com.example.plugin",
      contributionId: "my.handler",
      hookKey: "app.started",
    });
    expect(contrib.priority).toBe(50);
    expect(contrib.handler).toBe("");
  });
});

describe("PluginManifest", () => {
  it("creates with minimal params", () => {
    const manifest = new PluginManifest({
      manifestVersion: "1",
      pluginId: "com.example.test",
      pluginVersion: new SemVer(1, 0, 0),
      requiresSwitchboard: ApiRange.parse(">=0.1.0,<1.0.0"),
      entrypoint: "test_plugin:TestPlugin",
    });
    expect(manifest.name).toBe("");
    expect(manifest.contributions.slots).toEqual([]);
    expect(manifest.contributions.hooks).toEqual([]);
  });

  it("creates with contributions", () => {
    const slotContrib = new SlotContribution({
      pluginId: "com.example.test",
      contributionId: "sidebar",
      slotKey: "ui.sidebar",
    });
    const hookContrib = new HookContribution({
      pluginId: "com.example.test",
      contributionId: "startup",
      hookKey: "app.started",
    });
    const manifest = new PluginManifest({
      manifestVersion: "1",
      pluginId: "com.example.test",
      pluginVersion: new SemVer(1, 0, 0),
      requiresSwitchboard: ApiRange.parse(">=0.1.0"),
      entrypoint: "test_plugin:TestPlugin",
      contributions: new ManifestContributions({
        slots: [slotContrib],
        hooks: [hookContrib],
      }),
    });
    expect(manifest.contributions.slots.length).toBe(1);
    expect(manifest.contributions.hooks.length).toBe(1);
  });

  it("rejects missing manifest_version", () => {
    expect(
      () =>
        new PluginManifest({
          manifestVersion: "",
          pluginId: "com.example.test",
          pluginVersion: new SemVer(1, 0, 0),
          requiresSwitchboard: ApiRange.parse(">=0.1.0"),
          entrypoint: "test:Test",
        }),
    ).toThrow("manifest_version is required");
  });
});
