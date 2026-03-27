import { describe, it, expect } from "vitest";
import { LifecycleError } from "../../src/domain/errors.js";
import { PluginLifecycle, PluginState } from "../../src/domain/lifecycle.js";

describe("PluginLifecycle", () => {
  it("starts in READY state", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    expect(lifecycle.state).toBe(PluginState.READY);
    expect(lifecycle.isActive).toBe(false);
    expect(lifecycle.isFailed).toBe(false);
  });

  it("follows activation flow", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");

    lifecycle.beginActivation();
    expect(lifecycle.state).toBe(PluginState.STARTING);

    lifecycle.completeActivation();
    expect(lifecycle.state).toBe(PluginState.ACTIVE);
    expect(lifecycle.isActive).toBe(true);
  });

  it("follows deactivation flow", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();
    lifecycle.completeActivation();

    lifecycle.beginDeactivation();
    expect(lifecycle.state).toBe(PluginState.STOPPING);

    lifecycle.completeDeactivation();
    expect(lifecycle.state).toBe(PluginState.READY);
    expect(lifecycle.isActive).toBe(false);
  });

  it("rejects activation from wrong state", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation(); // Now STARTING

    try {
      lifecycle.beginActivation();
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(LifecycleError);
      const err = e as LifecycleError;
      expect(err.pluginId).toBe("com.example.plugin");
      expect(err.operation).toBe("activate");
      expect(err.currentState).toBe("starting");
    }
  });

  it("rejects deactivation from wrong state", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");

    try {
      lifecycle.beginDeactivation();
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(LifecycleError);
      const err = e as LifecycleError;
      expect(err.operation).toBe("deactivate");
      expect(err.currentState).toBe("ready");
    }
  });

  it("rolls back from STARTING", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();

    lifecycle.rollback();
    expect(lifecycle.state).toBe(PluginState.READY);
  });

  it("rejects rollback from wrong state", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");

    try {
      lifecycle.rollback();
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(LifecycleError);
      expect((e as LifecycleError).operation).toBe("rollback");
    }
  });

  it("fails from STARTING", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();

    const error = new Error("Import failed");
    lifecycle.fail(error);

    expect(lifecycle.state).toBe(PluginState.FAILED);
    expect(lifecycle.isFailed).toBe(true);
    expect(lifecycle.lastError).toBe(error);
  });

  it("fails from ACTIVE", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();
    lifecycle.completeActivation();

    const error = new Error("Runtime crash");
    lifecycle.fail(error);

    expect(lifecycle.state).toBe(PluginState.FAILED);
    expect(lifecycle.lastError).toBe(error);
  });

  it("clears instance on fail", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();
    lifecycle.instance = {};
    lifecycle.completeActivation();

    lifecycle.fail(new Error("crash"));
    expect(lifecycle.instance).toBeNull();
  });

  it("resets from FAILED", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();
    lifecycle.fail(new Error("error"));

    lifecycle.reset();
    expect(lifecycle.state).toBe(PluginState.READY);
    expect(lifecycle.lastError).toBeNull();
  });

  it("rejects reset from wrong state", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");

    try {
      lifecycle.reset();
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(LifecycleError);
      expect((e as LifecycleError).operation).toBe("reset");
    }
  });

  it("manages instance property", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    expect(lifecycle.instance).toBeNull();

    const instance = { name: "test" };
    lifecycle.instance = instance;
    expect(lifecycle.instance).toBe(instance);
  });

  it("clears instance on complete deactivation", () => {
    const lifecycle = new PluginLifecycle("com.example.plugin");
    lifecycle.beginActivation();
    lifecycle.instance = {};
    lifecycle.completeActivation();

    lifecycle.beginDeactivation();
    lifecycle.completeDeactivation();

    expect(lifecycle.instance).toBeNull();
  });
});
