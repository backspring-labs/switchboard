import { describe, it, expect } from "vitest";
import {
  SemVer,
  ApiRange,
  SlotDefinition,
  SlotPolicy,
  HookDefinition,
  HookKind,
  ManifestContributions,
  PluginManifest,
} from "../../src/domain/models.js";
import { PatchPanel } from "../../src/domain/patch-panel.js";
import { MemoryHookRouter } from "../../src/adapters/memory-hook-router.js";
import { RegistryLoader } from "../../src/adapters/registry-loader.js";

class FakePlugin {
  activate() {}
  deactivate() {}
}

function createPanel(): PatchPanel {
  const loader = new RegistryLoader();
  loader.registerEntrypoint("default", () => new FakePlugin());
  return new PatchPanel(
    [new SlotDefinition("ui.sidebar", { policy: SlotPolicy.MULTI })],
    [new HookDefinition("app.started", { kind: HookKind.LIFECYCLE })],
    { hookRouter: new MemoryHookRouter(), loader },
  );
}

function makeManifest(
  pluginId: string,
  options?: { requires?: string[]; optionalRequires?: string[] },
): PluginManifest {
  return new PluginManifest({
    manifestVersion: "1",
    pluginId,
    pluginVersion: new SemVer(1, 0, 0),
    requiresSwitchboard: ApiRange.parse(">=0.1.0,<1.0.0"),
    entrypoint: "default",
    contributions: new ManifestContributions(),
    requires: options?.requires,
    optionalRequires: options?.optionalRequires,
  });
}

describe("activationPlan()", () => {
  it("returns empty plan when no plugins", () => {
    const panel = createPanel();
    const plan = panel.activationPlan();
    expect(plan.order).toEqual([]);
    expect(plan.blocked).toEqual({});
    expect(plan.cycles).toEqual([]);
  });

  it("plans single plugin", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a"));
    const plan = panel.activationPlan();
    expect(plan.order).toEqual(["com.example.a"]);
  });

  it("respects dependencies", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.a"));
    const plan = panel.activationPlan();
    expect(plan.order.indexOf("com.example.a")).toBeLessThan(plan.order.indexOf("com.example.b"));
  });

  it("alphabetical tiebreak", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.c"));
    panel.registerManifest(makeManifest("com.example.a"));
    panel.registerManifest(makeManifest("com.example.b"));
    const plan = panel.activationPlan();
    expect([...plan.order]).toEqual(["com.example.a", "com.example.b", "com.example.c"]);
  });

  it("blocks on missing dependency", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a", { requires: ["com.example.missing"] }));
    const plan = panel.activationPlan();
    expect(plan.order).toEqual([]);
    expect(plan.blocked["com.example.a"]).toContain("missing");
  });

  it("detects cycle", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a", { requires: ["com.example.b"] }));
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.a"] }));
    const plan = panel.activationPlan();
    expect(plan.order).toEqual([]);
    expect("com.example.a" in plan.blocked).toBe(true);
    expect("com.example.b" in plan.blocked).toBe(true);
    expect(plan.cycles.length).toBeGreaterThan(0);
  });

  it("detects three-way cycle", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a", { requires: ["com.example.b"] }));
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.c"] }));
    panel.registerManifest(makeManifest("com.example.c", { requires: ["com.example.a"] }));
    const plan = panel.activationPlan();
    expect(plan.order).toEqual([]);
    expect(Object.keys(plan.blocked).length).toBe(3);
    expect(plan.cycles.length).toBeGreaterThan(0);
  });

  it("orders chain dependency", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.c", { requires: ["com.example.b"] }));
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.a"));
    const plan = panel.activationPlan();
    expect([...plan.order]).toEqual(["com.example.a", "com.example.b", "com.example.c"]);
  });

  it("optional_requires affects order", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.b", { optionalRequires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.a"));
    const plan = panel.activationPlan();
    expect(plan.order.indexOf("com.example.a")).toBeLessThan(plan.order.indexOf("com.example.b"));
  });

  it("missing optional does not block", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a", { optionalRequires: ["com.example.missing"] }));
    const plan = panel.activationPlan();
    expect([...plan.order]).toEqual(["com.example.a"]);
    expect(plan.blocked).toEqual({});
  });

  it("skips already active", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a"));
    panel.activate("com.example.a");
    panel.registerManifest(makeManifest("com.example.b"));
    const plan = panel.activationPlan();
    expect([...plan.order]).toEqual(["com.example.b"]);
  });

  it("handles diamond dependency", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a"));
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.c", { requires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.d", { requires: ["com.example.b", "com.example.c"] }));
    const plan = panel.activationPlan();
    expect(plan.order[0]).toBe("com.example.a");
    expect(plan.order[plan.order.length - 1]).toBe("com.example.d");
    expect(new Set(plan.order.slice(1, 3))).toEqual(new Set(["com.example.b", "com.example.c"]));
  });
});

describe("activateAll()", () => {
  it("activates single plugin", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a"));
    const plan = panel.activateAll();
    expect(plan.order).toContain("com.example.a");
    expect(panel.getPluginState("com.example.a")).toBe("active");
  });

  it("respects dependency order", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.a"));
    const plan = panel.activateAll();
    expect(plan.order.indexOf("com.example.a")).toBeLessThan(plan.order.indexOf("com.example.b"));
    expect(panel.getPluginState("com.example.a")).toBe("active");
    expect(panel.getPluginState("com.example.b")).toBe("active");
  });

  it("blocks on missing dependency", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a", { requires: ["com.example.missing"] }));
    const plan = panel.activateAll();
    expect(plan.order).toEqual([]);
    expect("com.example.a" in plan.blocked).toBe(true);
    expect(panel.getPluginState("com.example.a")).toBe("ready");
  });

  it("partial success — independent plugins activate", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a"));
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.missing"] }));
    const plan = panel.activateAll();
    expect(plan.order).toContain("com.example.a");
    expect("com.example.b" in plan.blocked).toBe(true);
  });

  it("dependent blocked when dependency fails activation", () => {
    const panel = createPanel();
    // Bad entrypoint — will fail activation
    panel.registerManifest(new PluginManifest({
      manifestVersion: "1",
      pluginId: "com.example.bad",
      pluginVersion: new SemVer(1, 0, 0),
      requiresSwitchboard: ApiRange.parse(">=0.1.0,<1.0.0"),
      entrypoint: "nonexistent",
      contributions: new ManifestContributions(),
    }));
    panel.registerManifest(makeManifest("com.example.dependent", { requires: ["com.example.bad"] }));
    const plan = panel.activateAll();
    expect("com.example.bad" in plan.blocked).toBe(true);
    expect("com.example.dependent" in plan.blocked).toBe(true);
    expect(plan.blocked["com.example.bad"]).toContain("activation failed");
  });

  it("is idempotent", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a"));
    const plan1 = panel.activateAll();
    const plan2 = panel.activateAll();
    expect(plan1.order).toContain("com.example.a");
    expect(plan2.order).toEqual([]); // Already active
  });

  it("activates independent plugins despite cycles", () => {
    const panel = createPanel();
    panel.registerManifest(makeManifest("com.example.a", { requires: ["com.example.b"] }));
    panel.registerManifest(makeManifest("com.example.b", { requires: ["com.example.a"] }));
    panel.registerManifest(makeManifest("com.example.c"));
    const plan = panel.activateAll();
    expect(plan.order).toContain("com.example.c");
    expect(panel.getPluginState("com.example.c")).toBe("active");
    expect("com.example.a" in plan.blocked).toBe(true);
    expect("com.example.b" in plan.blocked).toBe(true);
  });
});
