import { describe, it, expect } from "vitest";
import * as switchboard from "../../src/index.js";

describe("Public API exports", () => {
  it("exports VERSION", () => {
    expect(typeof switchboard.VERSION).toBe("string");
    expect(switchboard.VERSION.length).toBeGreaterThan(0);
  });

  it("exports domain models", () => {
    expect(switchboard.SemVer).toBeDefined();
    expect(switchboard.ApiRange).toBeDefined();
    expect(switchboard.SlotPolicy).toBeDefined();
    expect(switchboard.HookKind).toBeDefined();
    expect(switchboard.HookPolicy).toBeDefined();
    expect(switchboard.SlotDefinition).toBeDefined();
    expect(switchboard.HookDefinition).toBeDefined();
    expect(switchboard.Contribution).toBeDefined();
    expect(switchboard.SlotContribution).toBeDefined();
    expect(switchboard.HookContribution).toBeDefined();
    expect(switchboard.ManifestContributions).toBeDefined();
    expect(switchboard.PluginManifest).toBeDefined();
  });

  it("exports domain errors", () => {
    expect(switchboard.SwitchboardError).toBeDefined();
    expect(switchboard.PluginNotFoundError).toBeDefined();
    expect(switchboard.SlotNotFoundError).toBeDefined();
    expect(switchboard.HookNotFoundError).toBeDefined();
    expect(switchboard.CompatibilityError).toBeDefined();
    expect(switchboard.LifecycleError).toBeDefined();
    expect(switchboard.DuplicateRegistrationError).toBeDefined();
    expect(switchboard.ManifestError).toBeDefined();
    expect(switchboard.ContributionError).toBeDefined();
  });

  it("exports lifecycle", () => {
    expect(switchboard.PluginState).toBeDefined();
    expect(switchboard.PluginLifecycle).toBeDefined();
  });

  it("exports PatchPanel", () => {
    expect(switchboard.PatchPanel).toBeDefined();
  });

  it("exports adapters", () => {
    expect(switchboard.MemoryHookRouter).toBeDefined();
    expect(switchboard.RegistryLoader).toBeDefined();
  });

  it("exports parseManifest", () => {
    expect(switchboard.parseManifest).toBeDefined();
  });
});
