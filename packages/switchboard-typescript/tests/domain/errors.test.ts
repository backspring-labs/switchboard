import { describe, it, expect } from "vitest";
import {
  SwitchboardError,
  PluginNotFoundError,
  SlotNotFoundError,
  HookNotFoundError,
  CompatibilityError,
  LifecycleError,
  DuplicateRegistrationError,
  ManifestError,
  ContributionError,
} from "../../src/domain/errors.js";

describe("SwitchboardError", () => {
  it("is an instance of Error", () => {
    const err = new SwitchboardError("test");
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.message).toBe("test");
    expect(err.name).toBe("SwitchboardError");
  });
});

describe("PluginNotFoundError", () => {
  it("stores pluginId and formats message", () => {
    const err = new PluginNotFoundError("com.example.test");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.pluginId).toBe("com.example.test");
    expect(err.message).toBe("Plugin not found: com.example.test");
  });
});

describe("SlotNotFoundError", () => {
  it("stores slotKey and formats message", () => {
    const err = new SlotNotFoundError("ui.sidebar");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.slotKey).toBe("ui.sidebar");
    expect(err.message).toBe("Slot not found: ui.sidebar");
  });
});

describe("HookNotFoundError", () => {
  it("stores hookKey and formats message", () => {
    const err = new HookNotFoundError("app.started");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.hookKey).toBe("app.started");
    expect(err.message).toBe("Hook not found: app.started");
  });
});

describe("CompatibilityError", () => {
  it("stores fields and formats message", () => {
    const err = new CompatibilityError("com.test", ">=1.0.0", "0.3.0");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.pluginId).toBe("com.test");
    expect(err.required).toBe(">=1.0.0");
    expect(err.current).toBe("0.3.0");
    expect(err.message).toBe(
      "Plugin com.test requires switchboard >=1.0.0, but 0.3.0 is installed",
    );
  });
});

describe("LifecycleError", () => {
  it("stores fields and formats message", () => {
    const err = new LifecycleError("com.test", "activate", "starting");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.pluginId).toBe("com.test");
    expect(err.operation).toBe("activate");
    expect(err.currentState).toBe("starting");
    expect(err.message).toBe(
      "Cannot activate plugin com.test: currently in state 'starting'",
    );
  });
});

describe("DuplicateRegistrationError", () => {
  it("stores pluginId and formats message", () => {
    const err = new DuplicateRegistrationError("com.test");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.pluginId).toBe("com.test");
    expect(err.message).toBe("Plugin already registered: com.test");
  });
});

describe("ManifestError", () => {
  it("formats with plugin_id prefix", () => {
    const err = new ManifestError("bad field", "com.test");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.pluginId).toBe("com.test");
    expect(err.message).toBe("Plugin com.test: bad field");
  });

  it("formats without plugin_id prefix", () => {
    const err = new ManifestError("bad field");
    expect(err.pluginId).toBeUndefined();
    expect(err.message).toBe("bad field");
  });
});

describe("ContributionError", () => {
  it("formats with contribution_id prefix", () => {
    const err = new ContributionError("invalid", "my.contrib");
    expect(err).toBeInstanceOf(SwitchboardError);
    expect(err.contributionId).toBe("my.contrib");
    expect(err.message).toBe("Contribution my.contrib: invalid");
  });

  it("formats without contribution_id prefix", () => {
    const err = new ContributionError("invalid");
    expect(err.contributionId).toBeUndefined();
    expect(err.message).toBe("invalid");
  });
});
