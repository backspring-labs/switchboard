import { describe, it, expect } from "vitest";
import {
  SemVer,
  ApiRange,
  SlotDefinition,
  SlotPolicy,
  HookDefinition,
  HookKind,
  SlotContribution,
  HookContribution,
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
  loader.registerCallable("on_started", () => "started");
  return new PatchPanel(
    [
      new SlotDefinition("ui.sidebar", { policy: SlotPolicy.MULTI }),
      new SlotDefinition("ui.main", { policy: SlotPolicy.SINGLE }),
    ],
    [
      new HookDefinition("app.started", { kind: HookKind.LIFECYCLE }),
      new HookDefinition("command.run", { kind: HookKind.COMMAND }),
    ],
    { hookRouter: new MemoryHookRouter(), loader },
  );
}

function sampleManifest(): PluginManifest {
  return new PluginManifest({
    manifestVersion: "1",
    pluginId: "com.example.test",
    pluginVersion: new SemVer(1, 0, 0),
    requiresSwitchboard: ApiRange.parse(">=0.1.0,<1.0.0"),
    entrypoint: "default",
    contributions: new ManifestContributions(),
  });
}

function manifestWithContributions(): PluginManifest {
  return new PluginManifest({
    manifestVersion: "1",
    pluginId: "com.example.contrib",
    pluginVersion: new SemVer(2, 0, 0),
    requiresSwitchboard: ApiRange.parse(">=0.1.0,<1.0.0"),
    entrypoint: "default",
    contributions: new ManifestContributions({
      slots: [
        new SlotContribution({
          pluginId: "com.example.contrib",
          contributionId: "sidebar.widget",
          slotKey: "ui.sidebar",
          priority: 75,
        }),
      ],
      hooks: [
        new HookContribution({
          pluginId: "com.example.contrib",
          contributionId: "on.started",
          hookKey: "app.started",
          handler: "on_started",
          priority: 60,
        }),
      ],
    }),
  });
}

describe("runtimeInfo()", () => {
  it("returns framework version", () => {
    const info = createPanel().runtimeInfo();
    expect(typeof info.frameworkVersion).toBe("string");
    expect(info.frameworkVersion.length).toBeGreaterThan(0);
  });

  it("returns platform version", () => {
    const info = createPanel().runtimeInfo();
    expect(typeof info.platformVersion).toBe("string");
    expect(info.platformVersion.length).toBeGreaterThan(0);
  });

  it("returns slot and hook counts", () => {
    const info = createPanel().runtimeInfo();
    expect(info.slotCount).toBe(2);
    expect(info.hookCount).toBe(2);
  });

  it("returns zero plugin counts when empty", () => {
    const info = createPanel().runtimeInfo();
    expect(info.pluginCount).toBe(0);
    expect(info.activePluginCount).toBe(0);
  });

  it("increments plugin count after register", () => {
    const panel = createPanel();
    panel.registerManifest(sampleManifest());
    const info = panel.runtimeInfo();
    expect(info.pluginCount).toBe(1);
    expect(info.activePluginCount).toBe(0);
  });

  it("increments active count after activate", () => {
    const panel = createPanel();
    panel.registerManifest(sampleManifest());
    panel.activate("com.example.test");
    const info = panel.runtimeInfo();
    expect(info.pluginCount).toBe(1);
    expect(info.activePluginCount).toBe(1);
  });

  it("never throws on minimal panel", () => {
    const panel = new PatchPanel([], []);
    const info = panel.runtimeInfo();
    expect(info.slotCount).toBe(0);
    expect(info.hookCount).toBe(0);
  });
});

describe("snapshot()", () => {
  it("returns ISO timestamp", () => {
    const snap = createPanel().snapshot();
    expect(snap.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("includes runtime info", () => {
    const snap = createPanel().snapshot();
    expect(snap.runtime.slotCount).toBe(2);
    expect(snap.runtime.hookCount).toBe(2);
  });

  it("shows empty plugins when none registered", () => {
    const snap = createPanel().snapshot();
    expect(snap.plugins).toEqual([]);
  });

  it("shows registered plugin", () => {
    const panel = createPanel();
    panel.registerManifest(sampleManifest());
    const snap = panel.snapshot();
    expect(snap.plugins.length).toBe(1);
    expect(snap.plugins[0]!.pluginId).toBe("com.example.test");
    expect(snap.plugins[0]!.version).toBe("1.0.0");
    expect(snap.plugins[0]!.state).toBe("ready");
  });

  it("shows active state after activation", () => {
    const panel = createPanel();
    panel.registerManifest(sampleManifest());
    panel.activate("com.example.test");
    const snap = panel.snapshot();
    expect(snap.plugins[0]!.state).toBe("active");
  });

  it("shows all defined slots", () => {
    const snap = createPanel().snapshot();
    expect(snap.slots.length).toBe(2);
    const slotKeys = new Set(snap.slots.map((s) => s.slotKey));
    expect(slotKeys).toEqual(new Set(["ui.sidebar", "ui.main"]));
  });

  it("shows slot policy", () => {
    const snap = createPanel().snapshot();
    const sidebar = snap.slots.find((s) => s.slotKey === "ui.sidebar")!;
    expect(sidebar.policy).toBe("multi");
    const main = snap.slots.find((s) => s.slotKey === "ui.main")!;
    expect(main.policy).toBe("single");
  });

  it("shows all defined hooks", () => {
    const snap = createPanel().snapshot();
    expect(snap.hooks.length).toBe(2);
    const hookKeys = new Set(snap.hooks.map((h) => h.hookKey));
    expect(hookKeys).toEqual(new Set(["app.started", "command.run"]));
  });

  it("shows hook kind and effective policy", () => {
    const snap = createPanel().snapshot();
    const started = snap.hooks.find((h) => h.hookKey === "app.started")!;
    expect(started.kind).toBe("lifecycle");
    expect(started.policy).toBe("broadcast");
    const command = snap.hooks.find((h) => h.hookKey === "command.run")!;
    expect(command.kind).toBe("command");
    expect(command.policy).toBe("first_result");
  });

  it("shows slot contributions from active plugins", () => {
    const panel = createPanel();
    panel.registerManifest(manifestWithContributions());
    panel.activate("com.example.contrib");
    const snap = panel.snapshot();
    const sidebar = snap.slots.find((s) => s.slotKey === "ui.sidebar")!;
    expect(sidebar.contributions.length).toBe(1);
    expect(sidebar.contributions[0]!.contributionId).toBe("sidebar.widget");
    expect(sidebar.contributions[0]!.pluginId).toBe("com.example.contrib");
    expect(sidebar.contributions[0]!.priority).toBe(75);
  });

  it("shows hook handlers from active plugins", () => {
    const panel = createPanel();
    panel.registerManifest(manifestWithContributions());
    panel.activate("com.example.contrib");
    const snap = panel.snapshot();
    const started = snap.hooks.find((h) => h.hookKey === "app.started")!;
    expect(started.handlers.length).toBe(1);
    expect(started.handlers[0]!.contributionId).toBe("on.started");
    expect(started.handlers[0]!.priority).toBe(60);
  });

  it("excludes inactive plugin contributions", () => {
    const panel = createPanel();
    panel.registerManifest(manifestWithContributions());
    // Not activated
    const snap = panel.snapshot();
    const sidebar = snap.slots.find((s) => s.slotKey === "ui.sidebar")!;
    expect(sidebar.contributions.length).toBe(0);
  });

  it("shows contribution IDs on plugin snapshot", () => {
    const panel = createPanel();
    panel.registerManifest(manifestWithContributions());
    const snap = panel.snapshot();
    const plugin = snap.plugins[0]!;
    expect(plugin.contributions).toContain("sidebar.widget");
    expect(plugin.contributions).toContain("on.started");
  });

  it("is deterministic", () => {
    const panel = createPanel();
    const snap1 = panel.snapshot();
    const snap2 = panel.snapshot();
    expect(snap1.slots.map((s) => s.slotKey)).toEqual(snap2.slots.map((s) => s.slotKey));
    expect(snap1.hooks.map((h) => h.hookKey)).toEqual(snap2.hooks.map((h) => h.hookKey));
  });
});

describe("dumpState()", () => {
  it("returns string", () => {
    const result = createPanel().dumpState();
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("default is text", () => {
    const text = createPanel().dumpState();
    expect(text).toContain("=== Switchboard Runtime State ===");
  });

  it("text format is human-readable", () => {
    const text = createPanel().dumpState("text");
    expect(text).toContain("Timestamp:");
    expect(text).toContain("Runtime:");
    expect(text).toContain("Plugins:");
    expect(text).toContain("Slots:");
    expect(text).toContain("Hooks:");
  });

  it("json format is valid JSON", () => {
    const result = createPanel().dumpState("json");
    const data = JSON.parse(result);
    expect(data.timestamp).toBeDefined();
    expect(data.runtime).toBeDefined();
    expect(data.plugins).toBeDefined();
    expect(data.slots).toBeDefined();
    expect(data.hooks).toBeDefined();
  });

  it("json has runtime info", () => {
    const data = JSON.parse(createPanel().dumpState("json"));
    expect(data.runtime.framework_version).toBeDefined();
    expect(data.runtime.slot_count).toBe(2);
    expect(data.runtime.hook_count).toBe(2);
  });

  it("json timestamp is ISO format", () => {
    const data = JSON.parse(createPanel().dumpState("json"));
    expect(data.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("text shows registered plugins", () => {
    const panel = createPanel();
    panel.registerManifest(sampleManifest());
    const text = panel.dumpState();
    expect(text).toContain("com.example.test");
    expect(text).toContain("[ready]");
  });

  it("text shows active state", () => {
    const panel = createPanel();
    panel.registerManifest(sampleManifest());
    panel.activate("com.example.test");
    const text = panel.dumpState();
    expect(text).toContain("[active]");
  });

  it("json shows contributions", () => {
    const panel = createPanel();
    panel.registerManifest(manifestWithContributions());
    panel.activate("com.example.contrib");
    const data = JSON.parse(panel.dumpState("json"));
    const sidebar = data.slots.find((s: Record<string, unknown>) => s.slot_key === "ui.sidebar");
    expect(sidebar.contributions.length).toBe(1);
    expect(sidebar.contributions[0].contribution_id).toBe("sidebar.widget");
  });

  it("is deterministic (except timestamp)", () => {
    const panel = createPanel();
    const text1 = panel.dumpState();
    const text2 = panel.dumpState();
    const lines1 = text1.split("\n").filter((l) => !l.startsWith("Timestamp:"));
    const lines2 = text2.split("\n").filter((l) => !l.startsWith("Timestamp:"));
    expect(lines1).toEqual(lines2);
  });

  it("json has sorted keys", () => {
    const result = createPanel().dumpState("json");
    const data = JSON.parse(result);
    const reserialized = JSON.stringify(data, null, 2);
    expect(result).toBe(reserialized);
  });
});
