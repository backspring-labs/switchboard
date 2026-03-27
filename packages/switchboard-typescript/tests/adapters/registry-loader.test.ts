import { describe, it, expect } from "vitest";
import { RegistryLoader } from "../../src/adapters/registry-loader.js";

describe("RegistryLoader", () => {
  it("loads registered entrypoint", () => {
    const loader = new RegistryLoader();
    loader.registerEntrypoint("my-plugin", () => ({ name: "test" }));

    const instance = loader.loadEntrypoint("my-plugin") as { name: string };
    expect(instance.name).toBe("test");
  });

  it("loads registered callable", () => {
    const loader = new RegistryLoader();
    const fn = (x: unknown) => `result:${x}`;
    loader.registerCallable("my-handler", fn as (...args: unknown[]) => unknown);

    const loaded = loader.loadCallable("my-handler");
    expect(loaded("42")).toBe("result:42");
  });

  it("throws for unregistered entrypoint", () => {
    const loader = new RegistryLoader();
    expect(() => loader.loadEntrypoint("missing")).toThrow(
      "Entrypoint not registered: 'missing'",
    );
  });

  it("throws for unregistered callable", () => {
    const loader = new RegistryLoader();
    expect(() => loader.loadCallable("missing")).toThrow(
      "Callable not registered: 'missing'",
    );
  });

  it("overwrites existing registration", () => {
    const loader = new RegistryLoader();
    loader.registerEntrypoint("key", () => "first");
    loader.registerEntrypoint("key", () => "second");

    expect(loader.loadEntrypoint("key")).toBe("second");
  });
});
