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
import { PluginState } from "../../src/domain/lifecycle.js";
import { PatchPanel } from "../../src/domain/patch-panel.js";
import { MemoryHookRouter } from "../../src/adapters/memory-hook-router.js";
import { RegistryLoader } from "../../src/adapters/registry-loader.js";

class SamplePlugin {
  activated = false;
  deactivated = false;
  activate(_ctx: Record<string, unknown>) { this.activated = true; }
  deactivate(_ctx: Record<string, unknown>) { this.deactivated = true; }
}

function makeManifest(
  pluginId: string,
  options?: { slots?: SlotContribution[]; hooks?: HookContribution[] },
): PluginManifest {
  return new PluginManifest({
    manifestVersion: "1",
    pluginId,
    pluginVersion: SemVer.parse("1.0.0"),
    requiresSwitchboard: ApiRange.parse(">=0.1.0,<1.0.0"),
    entrypoint: pluginId,
    contributions: new ManifestContributions({
      slots: options?.slots,
      hooks: options?.hooks,
    }),
  });
}

describe("Golden Path", () => {
  it("complete flow: register, activate, resolve, emit, deactivate", () => {
    const router = new MemoryHookRouter();
    const loader = new RegistryLoader();
    loader.registerEntrypoint("com.example.test", () => new SamplePlugin());
    loader.registerCallable("on_app_started", (payload: unknown) => {
      const p = payload as Record<string, unknown>;
      return `started:${p.timestamp}`;
    });

    const panel = new PatchPanel(
      [
        new SlotDefinition("ui.sidebar", { policy: SlotPolicy.MULTI }),
        new SlotDefinition("ui.main", { policy: SlotPolicy.SINGLE }),
      ],
      [
        new HookDefinition("app.started", { kind: HookKind.LIFECYCLE }),
        new HookDefinition("command.run", { kind: HookKind.COMMAND }),
      ],
      { hookRouter: router, loader },
    );

    // Register
    const slotContrib = new SlotContribution({
      pluginId: "com.example.test",
      contributionId: "sidebar.widget",
      slotKey: "ui.sidebar",
      priority: 50,
    });
    const hookContrib = new HookContribution({
      pluginId: "com.example.test",
      contributionId: "on.started",
      hookKey: "app.started",
      priority: 50,
      handler: "on_app_started",
    });
    panel.registerManifest(
      makeManifest("com.example.test", { slots: [slotContrib], hooks: [hookContrib] }),
    );

    // Activate
    panel.activate("com.example.test");

    // Resolve slot
    const sidebarItems = panel.resolveSlot("ui.sidebar");
    expect(sidebarItems.length).toBe(1);
    expect(sidebarItems[0]!.pluginId).toBe("com.example.test");
    expect(sidebarItems[0]!.contributionId).toBe("sidebar.widget");

    // Emit hook
    const results = panel.emit("app.started", { timestamp: 12345 });
    expect(results).toEqual(["started:12345"]);

    // Deactivate
    panel.deactivate("com.example.test");
    expect(panel.getPluginState("com.example.test")).toBe(PluginState.READY);
    expect(panel.resolveSlot("ui.sidebar").length).toBe(0);

    // Unregister
    panel.unregister("com.example.test");
    expect(panel.listPlugins()).toEqual([]);
  });

  it("multiple plugins ordered by priority", () => {
    const router = new MemoryHookRouter();
    const loader = new RegistryLoader();
    loader.registerEntrypoint("com.example.a", () => new SamplePlugin());
    loader.registerEntrypoint("com.example.b", () => new SamplePlugin());
    loader.registerCallable("handler_a", (payload: unknown) => {
      return `a:${(payload as Record<string, unknown>).timestamp}`;
    });
    loader.registerCallable("handler_b", (payload: unknown) => {
      return `b:${(payload as Record<string, unknown>).timestamp}`;
    });

    const panel = new PatchPanel(
      [new SlotDefinition("ui.sidebar")],
      [new HookDefinition("app.started", { kind: HookKind.LIFECYCLE })],
      { hookRouter: router, loader },
    );

    // Plugin A (low priority)
    panel.registerManifest(
      makeManifest("com.example.a", {
        slots: [
          new SlotContribution({ pluginId: "com.example.a", contributionId: "widget", slotKey: "ui.sidebar", priority: 10 }),
        ],
        hooks: [
          new HookContribution({ pluginId: "com.example.a", contributionId: "handler", hookKey: "app.started", priority: 10, handler: "handler_a" }),
        ],
      }),
    );
    panel.activate("com.example.a");

    // Plugin B (high priority)
    panel.registerManifest(
      makeManifest("com.example.b", {
        slots: [
          new SlotContribution({ pluginId: "com.example.b", contributionId: "widget", slotKey: "ui.sidebar", priority: 100 }),
        ],
        hooks: [
          new HookContribution({ pluginId: "com.example.b", contributionId: "handler", hookKey: "app.started", priority: 100, handler: "handler_b" }),
        ],
      }),
    );
    panel.activate("com.example.b");

    // Verify slot ordering
    const slots = panel.resolveSlot("ui.sidebar");
    expect(slots.length).toBe(2);
    expect(slots[0]!.pluginId).toBe("com.example.b"); // priority 100
    expect(slots[1]!.pluginId).toBe("com.example.a"); // priority 10

    // Verify hook ordering
    const results = panel.emit("app.started", { timestamp: 999 });
    expect(results).toEqual(["b:999", "a:999"]);
  });

  it("SINGLE slot policy returns only highest priority", () => {
    const loader = new RegistryLoader();
    const router = new MemoryHookRouter();

    for (const id of ["com.low", "com.high", "com.mid"]) {
      loader.registerEntrypoint(id, () => new SamplePlugin());
    }

    const panel = new PatchPanel(
      [new SlotDefinition("ui.main", { policy: SlotPolicy.SINGLE })],
      [],
      { hookRouter: router, loader },
    );

    for (const [pluginId, priority] of [["com.low", 10], ["com.high", 100], ["com.mid", 50]] as const) {
      panel.registerManifest(
        makeManifest(pluginId, {
          slots: [new SlotContribution({ pluginId, contributionId: "main", slotKey: "ui.main", priority })],
        }),
      );
      panel.activate(pluginId);
    }

    const result = panel.resolveSlot("ui.main");
    expect(result.length).toBe(1);
    expect(result[0]!.pluginId).toBe("com.high");
  });

  it("FIRST_RESULT hook policy returns first non-null", () => {
    const router = new MemoryHookRouter();
    const loader = new RegistryLoader();
    loader.registerEntrypoint("com.main", () => new SamplePlugin());
    loader.registerEntrypoint("com.fallback", () => new SamplePlugin());
    loader.registerCallable("cmd_main", (payload: unknown) => {
      const p = payload as Record<string, unknown>;
      if (p.command === "greet") return { greeting: `Hello, ${p.name}!` };
      return null;
    });
    loader.registerCallable("cmd_fallback", () => ({ error: "Unknown command" }));

    const panel = new PatchPanel(
      [],
      [new HookDefinition("command.run", { kind: HookKind.COMMAND })],
      { hookRouter: router, loader },
    );

    panel.registerManifest(
      makeManifest("com.main", {
        hooks: [new HookContribution({ pluginId: "com.main", contributionId: "cmd", hookKey: "command.run", priority: 100, handler: "cmd_main" })],
      }),
    );
    panel.activate("com.main");

    panel.registerManifest(
      makeManifest("com.fallback", {
        hooks: [new HookContribution({ pluginId: "com.fallback", contributionId: "cmd", hookKey: "command.run", priority: 10, handler: "cmd_fallback" })],
      }),
    );
    panel.activate("com.fallback");

    // Matching command
    expect(panel.emit("command.run", { command: "greet", name: "Alice" })).toEqual({ greeting: "Hello, Alice!" });

    // Falls through to fallback
    expect(panel.emit("command.run", { command: "unknown" })).toEqual({ error: "Unknown command" });
  });
});
