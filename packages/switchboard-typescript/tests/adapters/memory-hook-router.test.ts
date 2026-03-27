import { describe, it, expect } from "vitest";
import { HookContribution, HookPolicy } from "../../src/domain/models.js";
import { MemoryHookRouter } from "../../src/adapters/memory-hook-router.js";

describe("MemoryHookRouter", () => {
  it("registers and emits with broadcast", () => {
    const router = new MemoryHookRouter();
    const callOrder: string[] = [];

    const handler1 = () => {
      callOrder.push("h1");
      return "result1";
    };
    const handler2 = () => {
      callOrder.push("h2");
      return "result2";
    };

    const contrib1 = new HookContribution({
      pluginId: "plugin.a",
      contributionId: "h1",
      hookKey: "test.hook",
      priority: 50,
    });
    const contrib2 = new HookContribution({
      pluginId: "plugin.b",
      contributionId: "h2",
      hookKey: "test.hook",
      priority: 100,
    });

    router.registerHandler("test.hook", contrib1, handler1);
    router.registerHandler("test.hook", contrib2, handler2);

    const results = router.emit("test.hook", HookPolicy.BROADCAST, {});

    // Higher priority first
    expect(callOrder).toEqual(["h2", "h1"]);
    expect(results).toEqual(["result2", "result1"]);
  });

  it("first_result returns first non-null", () => {
    const router = new MemoryHookRouter();

    const returnsNull = () => null;
    const returnsValue = () => "found";
    const shouldNotBeCalled = () => {
      throw new Error("Should not be called");
    };

    const contrib1 = new HookContribution({
      pluginId: "a",
      contributionId: "h1",
      hookKey: "cmd",
      priority: 100,
    });
    const contrib2 = new HookContribution({
      pluginId: "b",
      contributionId: "h2",
      hookKey: "cmd",
      priority: 50,
    });
    const contrib3 = new HookContribution({
      pluginId: "c",
      contributionId: "h3",
      hookKey: "cmd",
      priority: 10,
    });

    router.registerHandler("cmd", contrib1, returnsNull);
    router.registerHandler("cmd", contrib2, returnsValue);
    router.registerHandler("cmd", contrib3, shouldNotBeCalled);

    const result = router.emit("cmd", HookPolicy.FIRST_RESULT, {});
    expect(result).toBe("found");
  });

  it("first_result returns null if all return null", () => {
    const router = new MemoryHookRouter();

    const returnsNull = () => null;
    const contrib = new HookContribution({
      pluginId: "a",
      contributionId: "h1",
      hookKey: "cmd",
      priority: 50,
    });
    router.registerHandler("cmd", contrib, returnsNull);

    const result = router.emit("cmd", HookPolicy.FIRST_RESULT, {});
    expect(result).toBeNull();
  });

  it("emits to empty hook", () => {
    const router = new MemoryHookRouter();

    const broadcastResult = router.emit("empty", HookPolicy.BROADCAST, {});
    expect(broadcastResult).toEqual([]);

    const firstResult = router.emit("empty", HookPolicy.FIRST_RESULT, {});
    expect(firstResult).toBeNull();
  });

  it("unregisters handler", () => {
    const router = new MemoryHookRouter();
    const handler = () => "result";
    const contrib = new HookContribution({
      pluginId: "a",
      contributionId: "h1",
      hookKey: "test",
      priority: 50,
    });

    router.registerHandler("test", contrib, handler);
    expect(router.emit("test", HookPolicy.BROADCAST, {})).toEqual(["result"]);

    router.unregisterHandler("test", "h1");
    expect(router.emit("test", HookPolicy.BROADCAST, {})).toEqual([]);
  });

  it("unregisters from nonexistent hook without error", () => {
    const router = new MemoryHookRouter();
    router.unregisterHandler("nonexistent", "h1"); // Should not throw
  });

  it("clears all handlers", () => {
    const router = new MemoryHookRouter();
    const handler = () => "result";
    const contrib = new HookContribution({
      pluginId: "a",
      contributionId: "h1",
      hookKey: "test",
      priority: 50,
    });

    router.registerHandler("test", contrib, handler);
    router.clear();
    expect(router.emit("test", HookPolicy.BROADCAST, {})).toEqual([]);
  });

  it("broadcast continues on error (failure isolation)", () => {
    const router = new MemoryHookRouter();

    const raisesError = () => {
      throw new Error("boom");
    };
    const returnsValue = () => "success";

    const contrib1 = new HookContribution({
      pluginId: "a",
      contributionId: "h1",
      hookKey: "test",
      priority: 100,
    });
    const contrib2 = new HookContribution({
      pluginId: "b",
      contributionId: "h2",
      hookKey: "test",
      priority: 50,
    });

    router.registerHandler("test", contrib1, raisesError);
    router.registerHandler("test", contrib2, returnsValue);

    const results = router.emit("test", HookPolicy.BROADCAST, {});
    expect(results).toEqual(["success"]);
  });

  it("first_result propagates errors", () => {
    const router = new MemoryHookRouter();

    const raisesError = () => {
      throw new Error("boom");
    };
    const contrib = new HookContribution({
      pluginId: "a",
      contributionId: "h1",
      hookKey: "test",
      priority: 50,
    });

    router.registerHandler("test", contrib, raisesError);

    expect(() => router.emit("test", HookPolicy.FIRST_RESULT, {})).toThrow(
      "boom",
    );
  });

  it("breaks ties by plugin_id then contribution_id", () => {
    const router = new MemoryHookRouter();
    const callOrder: string[] = [];

    const makeHandler = (name: string) => () => {
      callOrder.push(name);
      return name;
    };

    for (const pluginId of ["z.plugin", "a.plugin", "m.plugin"]) {
      const contrib = new HookContribution({
        pluginId,
        contributionId: "handler",
        hookKey: "test",
        priority: 50,
      });
      router.registerHandler("test", contrib, makeHandler(pluginId));
    }

    router.emit("test", HookPolicy.BROADCAST, {});
    expect(callOrder).toEqual(["a.plugin", "m.plugin", "z.plugin"]);
  });
});
