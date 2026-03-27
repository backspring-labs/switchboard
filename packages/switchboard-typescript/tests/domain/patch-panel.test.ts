import { describe, it, expect } from "vitest";
import {
  SemVer,
  ApiRange,
  SlotDefinition,
  SlotPolicy,
  HookDefinition,
  SlotContribution,
  HookContribution,
  ManifestContributions,
  PluginManifest,
  HookPolicy,
} from "../../src/domain/models.js";
import {
  CompatibilityError,
  DuplicateRegistrationError,
  HookNotFoundError,
  LifecycleError,
  PluginNotFoundError,
  SlotNotFoundError,
} from "../../src/domain/errors.js";
import { PluginState } from "../../src/domain/lifecycle.js";
import { PatchPanel } from "../../src/domain/patch-panel.js";
import type { HookRouterPort, LoaderPort } from "../../src/domain/ports.js";

// =============================================================================
// Test Helpers
// =============================================================================

class FakePlugin {
  activated = false;
  deactivated = false;
  activate(_ctx: Record<string, unknown>) {
    this.activated = true;
  }
  deactivate(_ctx: Record<string, unknown>) {
    this.deactivated = true;
  }
}

const fakeLoader: LoaderPort = {
  loadEntrypoint: () => new FakePlugin(),
  loadCallable: () => () => null,
};

const fakeRouter: HookRouterPort = {
  registerHandler: () => {},
  unregisterHandler: () => {},
  emit: () => [],
  clear: () => {},
};

function makeManifest(
  options?: {
    pluginId?: string;
    version?: string;
    requires?: string;
    slots?: SlotContribution[];
    hooks?: HookContribution[];
    requiresPlugins?: string[];
    optionalRequires?: string[];
  },
): PluginManifest {
  const pluginId = options?.pluginId ?? "com.example.test";
  return new PluginManifest({
    manifestVersion: "1",
    pluginId,
    pluginVersion: SemVer.parse(options?.version ?? "1.0.0"),
    requiresSwitchboard: ApiRange.parse(options?.requires ?? ">=0.1.0,<1.0.0"),
    entrypoint: `${pluginId}:Plugin`,
    contributions: new ManifestContributions({
      slots: options?.slots,
      hooks: options?.hooks,
    }),
    requires: options?.requiresPlugins,
    optionalRequires: options?.optionalRequires,
  });
}

// =============================================================================
// Tests
// =============================================================================

describe("PatchPanel creation", () => {
  it("creates empty panel", () => {
    const panel = new PatchPanel([], []);
    expect(panel.listPlugins()).toEqual([]);
    expect(panel.listSlots()).toEqual([]);
    expect(panel.listHooks()).toEqual([]);
  });

  it("creates with slots and hooks", () => {
    const panel = new PatchPanel(
      [new SlotDefinition("ui.sidebar"), new SlotDefinition("ui.main")],
      [new HookDefinition("app.started"), new HookDefinition("app.stopped")],
    );
    expect(new Set(panel.listSlots())).toEqual(
      new Set(["ui.sidebar", "ui.main"]),
    );
    expect(new Set(panel.listHooks())).toEqual(
      new Set(["app.started", "app.stopped"]),
    );
  });

  it("rejects duplicate slot key", () => {
    expect(
      () =>
        new PatchPanel(
          [new SlotDefinition("ui.sidebar"), new SlotDefinition("ui.sidebar")],
          [],
        ),
    ).toThrow("Duplicate slot key");
  });

  it("rejects duplicate hook key", () => {
    expect(
      () =>
        new PatchPanel(
          [],
          [new HookDefinition("app.started"), new HookDefinition("app.started")],
        ),
    ).toThrow("Duplicate hook key");
  });
});

describe("Plugin registration", () => {
  it("registers manifest", () => {
    const panel = new PatchPanel([], []);
    panel.registerManifest(makeManifest());

    expect(panel.listPlugins()).toContain("com.example.test");
    expect(panel.getPluginState("com.example.test")).toBe(PluginState.READY);
  });

  it("rejects duplicate registration", () => {
    const panel = new PatchPanel([], []);
    panel.registerManifest(makeManifest());

    try {
      panel.registerManifest(makeManifest());
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(DuplicateRegistrationError);
      expect((e as DuplicateRegistrationError).pluginId).toBe(
        "com.example.test",
      );
    }
  });

  it("rejects incompatible version", () => {
    const panel = new PatchPanel([], []);

    try {
      panel.registerManifest(makeManifest({ requires: ">=2.0.0" }));
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(CompatibilityError);
      expect((e as CompatibilityError).pluginId).toBe("com.example.test");
      expect((e as CompatibilityError).required).toContain(">=2.0.0");
    }
  });

  it("rejects unknown slot", () => {
    const panel = new PatchPanel([], []);
    const contrib = new SlotContribution({
      pluginId: "com.example.test",
      contributionId: "c1",
      slotKey: "ui.nonexistent",
    });

    try {
      panel.registerManifest(makeManifest({ slots: [contrib] }));
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(SlotNotFoundError);
      expect((e as SlotNotFoundError).slotKey).toBe("ui.nonexistent");
    }
  });

  it("rejects unknown hook", () => {
    const panel = new PatchPanel([], []);
    const contrib = new HookContribution({
      pluginId: "com.example.test",
      contributionId: "h1",
      hookKey: "event.nonexistent",
    });

    try {
      panel.registerManifest(makeManifest({ hooks: [contrib] }));
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HookNotFoundError);
      expect((e as HookNotFoundError).hookKey).toBe("event.nonexistent");
    }
  });

  it("unregisters plugin", () => {
    const panel = new PatchPanel([], []);
    panel.registerManifest(makeManifest());
    panel.unregister("com.example.test");
    expect(panel.listPlugins()).not.toContain("com.example.test");
  });

  it("rejects unregistering unknown plugin", () => {
    const panel = new PatchPanel([], []);
    expect(() => panel.unregister("nonexistent")).toThrow(PluginNotFoundError);
  });
});

describe("Slot resolution", () => {
  it("resolves empty slot", () => {
    const panel = new PatchPanel([new SlotDefinition("ui.sidebar")], []);
    expect(panel.resolveSlot("ui.sidebar")).toEqual([]);
  });

  it("rejects unknown slot", () => {
    const panel = new PatchPanel([], []);
    expect(() => panel.resolveSlot("nonexistent")).toThrow(SlotNotFoundError);
  });

  it("only returns active contributions", () => {
    const panel = new PatchPanel([new SlotDefinition("ui.sidebar")], []);
    const contrib = new SlotContribution({
      pluginId: "com.example.test",
      contributionId: "c1",
      slotKey: "ui.sidebar",
    });
    panel.registerManifest(makeManifest({ slots: [contrib] }));

    // READY, not ACTIVE
    expect(panel.resolveSlot("ui.sidebar")).toEqual([]);
  });

  it("orders by priority", () => {
    const panel = new PatchPanel([new SlotDefinition("ui.sidebar")], [], {
      loader: fakeLoader,
    });

    const contribA = new SlotContribution({
      pluginId: "com.example.a",
      contributionId: "c1",
      slotKey: "ui.sidebar",
      priority: 10,
    });
    panel.registerManifest(
      makeManifest({ pluginId: "com.example.a", slots: [contribA] }),
    );
    panel.activate("com.example.a");

    const contribB = new SlotContribution({
      pluginId: "com.example.b",
      contributionId: "c1",
      slotKey: "ui.sidebar",
      priority: 100,
    });
    panel.registerManifest(
      makeManifest({ pluginId: "com.example.b", slots: [contribB] }),
    );
    panel.activate("com.example.b");

    const result = panel.resolveSlot("ui.sidebar");
    expect(result.length).toBe(2);
    expect(result[0]!.pluginId).toBe("com.example.b");
    expect(result[1]!.pluginId).toBe("com.example.a");
  });

  it("breaks ties by plugin_id", () => {
    const panel = new PatchPanel([new SlotDefinition("ui.sidebar")], [], {
      loader: fakeLoader,
    });

    for (const pluginId of ["com.example.z", "com.example.a"]) {
      const contrib = new SlotContribution({
        pluginId,
        contributionId: "c1",
        slotKey: "ui.sidebar",
        priority: 50,
      });
      panel.registerManifest(makeManifest({ pluginId, slots: [contrib] }));
      panel.activate(pluginId);
    }

    const result = panel.resolveSlot("ui.sidebar");
    expect(result[0]!.pluginId).toBe("com.example.a");
    expect(result[1]!.pluginId).toBe("com.example.z");
  });

  it("SINGLE policy returns one", () => {
    const panel = new PatchPanel(
      [new SlotDefinition("ui.main", { policy: SlotPolicy.SINGLE })],
      [],
      { loader: fakeLoader },
    );

    for (const [pluginId, priority] of [
      ["com.a", 10],
      ["com.b", 100],
      ["com.c", 50],
    ] as const) {
      const contrib = new SlotContribution({
        pluginId,
        contributionId: "c1",
        slotKey: "ui.main",
        priority,
      });
      panel.registerManifest(makeManifest({ pluginId, slots: [contrib] }));
      panel.activate(pluginId);
    }

    const result = panel.resolveSlot("ui.main");
    expect(result.length).toBe(1);
    expect(result[0]!.pluginId).toBe("com.b");
  });
});

describe("Plugin activation", () => {
  it("requires loader", () => {
    const panel = new PatchPanel([], []);
    panel.registerManifest(makeManifest());

    expect(() => panel.activate("com.example.test")).toThrow(
      "No loader configured",
    );
  });

  it("rejects unknown plugin", () => {
    const panel = new PatchPanel([], [], { loader: fakeLoader });
    expect(() => panel.activate("nonexistent")).toThrow(PluginNotFoundError);
  });

  it("activates successfully", () => {
    const panel = new PatchPanel([], [], { loader: fakeLoader });
    panel.registerManifest(makeManifest());
    panel.activate("com.example.test");

    expect(panel.getPluginState("com.example.test")).toBe(PluginState.ACTIVE);
  });

  it("rejects double activation", () => {
    const panel = new PatchPanel([], [], { loader: fakeLoader });
    panel.registerManifest(makeManifest());
    panel.activate("com.example.test");

    expect(() => panel.activate("com.example.test")).toThrow(LifecycleError);
  });

  it("deactivates successfully", () => {
    const panel = new PatchPanel([], [], { loader: fakeLoader });
    panel.registerManifest(makeManifest());
    panel.activate("com.example.test");
    panel.deactivate("com.example.test");

    expect(panel.getPluginState("com.example.test")).toBe(PluginState.READY);
  });

  it("rejects deactivating non-active plugin", () => {
    const panel = new PatchPanel([], [], { loader: fakeLoader });
    panel.registerManifest(makeManifest());

    expect(() => panel.deactivate("com.example.test")).toThrow(LifecycleError);
  });

  it("rejects unregistering active plugin", () => {
    const panel = new PatchPanel([], [], { loader: fakeLoader });
    panel.registerManifest(makeManifest());
    panel.activate("com.example.test");

    expect(() => panel.unregister("com.example.test")).toThrow(LifecycleError);
  });

  it("deactivation removes contributions", () => {
    const panel = new PatchPanel([new SlotDefinition("ui.sidebar")], [], {
      loader: fakeLoader,
    });
    const contrib = new SlotContribution({
      pluginId: "com.example.test",
      contributionId: "c1",
      slotKey: "ui.sidebar",
    });
    panel.registerManifest(makeManifest({ slots: [contrib] }));
    panel.activate("com.example.test");
    expect(panel.resolveSlot("ui.sidebar").length).toBe(1);

    panel.deactivate("com.example.test");
    expect(panel.resolveSlot("ui.sidebar").length).toBe(0);
  });

  it("rollback cleans up partial registrations", () => {
    const unregistered: string[] = [];

    const failingLoader: LoaderPort = {
      loadEntrypoint: () => new FakePlugin(),
      loadCallable: () => {
        throw new Error("Cannot load handler");
      },
    };

    const trackingRouter: HookRouterPort = {
      registerHandler: () => {},
      unregisterHandler: (_hookKey: string, contribId: string) => {
        unregistered.push(contribId);
      },
      emit: () => [],
      clear: () => {},
    };

    const panel = new PatchPanel(
      [new SlotDefinition("ui.sidebar")],
      [new HookDefinition("app.started")],
      { hookRouter: trackingRouter, loader: failingLoader },
    );

    const slotContrib = new SlotContribution({
      pluginId: "com.example.test",
      contributionId: "slot1",
      slotKey: "ui.sidebar",
    });
    const hookContrib = new HookContribution({
      pluginId: "com.example.test",
      contributionId: "hook1",
      hookKey: "app.started",
      handler: "some.module:handler",
    });

    panel.registerManifest(
      makeManifest({ slots: [slotContrib], hooks: [hookContrib] }),
    );

    expect(() => panel.activate("com.example.test")).toThrow(
      "Cannot load handler",
    );

    // Plugin rolled back to READY
    expect(panel.getPluginState("com.example.test")).toBe(PluginState.READY);

    // Slot contributions cleaned up
    expect(panel.resolveSlot("ui.sidebar").length).toBe(0);

    // Hook handler unregistration called
    expect(unregistered).toContain("hook1");
  });
});

describe("Hook emission", () => {
  it("requires router", () => {
    const panel = new PatchPanel([], [new HookDefinition("app.started")]);

    expect(() => panel.emit("app.started", {})).toThrow(
      "No hook router configured",
    );
  });

  it("rejects unknown hook", () => {
    const panel = new PatchPanel([], [], { hookRouter: fakeRouter });

    expect(() => panel.emit("nonexistent", {})).toThrow(HookNotFoundError);
  });
});

describe("Re-entrancy guard", () => {
  it("rejects mutation during hook emission", () => {
    let panelRef: PatchPanel;

    const reentrantRouter: HookRouterPort = {
      registerHandler: () => {},
      unregisterHandler: () => {},
      emit: () => {
        // Try to mutate during emission
        expect(() =>
          panelRef.registerManifest(
            makeManifest({ pluginId: "com.reentrant" }),
          ),
        ).toThrow(LifecycleError);
        return [];
      },
      clear: () => {},
    };

    panelRef = new PatchPanel([], [new HookDefinition("app.started")], {
      hookRouter: reentrantRouter,
    });

    panelRef.emit("app.started", {});
  });
});
