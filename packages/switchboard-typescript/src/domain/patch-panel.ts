import {
  CompatibilityError,
  DuplicateRegistrationError,
  HookNotFoundError,
  LifecycleError,
  PluginNotFoundError,
  SlotNotFoundError,
} from "./errors.js";
import { PluginLifecycle, PluginState } from "./lifecycle.js";
import {
  SemVer,
  SlotPolicy,
} from "./models.js";
import type {
  ActivationPlan,
  ContributionSnapshot,
  Contribution,
  HookContribution,
  HookDefinition,
  HookSnapshot,
  PluginManifest,
  PluginSnapshot,
  RuntimeInfo,
  RuntimeSnapshot,
  SlotContribution,
  SlotDefinition,
  SlotSnapshot,
} from "./models.js";
import type { HookRouterPort, LoaderPort } from "./ports.js";
import { VERSION } from "../version.js";

const SWITCHBOARD_VERSION = SemVer.parse(VERSION);

function getPlatformVersion(): string {
  try {
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    return (globalThis as Record<string, unknown>).process
      ? ((globalThis as Record<string, unknown>).process as { version: string }).version
      : "unknown";
  } catch {
    return "unknown";
  }
}

export class PatchPanel {
  private _slots: Map<string, SlotDefinition>;
  private _hooks: Map<string, HookDefinition>;
  private _plugins = new Map<
    string,
    { manifest: PluginManifest; lifecycle: PluginLifecycle }
  >();
  private _slotContributions: Map<string, SlotContribution[]>;
  private _hookContributions: Map<string, HookContribution[]>;
  private _hookRouter: HookRouterPort | undefined;
  private _loader: LoaderPort | undefined;
  private _inHookEmission = false;

  constructor(
    slots: SlotDefinition[],
    hooks: HookDefinition[],
    options?: {
      hookRouter?: HookRouterPort;
      loader?: LoaderPort;
    },
  ) {
    this._slots = new Map();
    for (const slot of slots) {
      if (this._slots.has(slot.slotKey)) {
        throw new Error(`Duplicate slot key: ${slot.slotKey}`);
      }
      this._slots.set(slot.slotKey, slot);
    }

    this._hooks = new Map();
    for (const hook of hooks) {
      if (this._hooks.has(hook.hookKey)) {
        throw new Error(`Duplicate hook key: ${hook.hookKey}`);
      }
      this._hooks.set(hook.hookKey, hook);
    }

    this._slotContributions = new Map();
    for (const key of this._slots.keys()) {
      this._slotContributions.set(key, []);
    }

    this._hookContributions = new Map();
    for (const key of this._hooks.keys()) {
      this._hookContributions.set(key, []);
    }

    this._hookRouter = options?.hookRouter;
    this._loader = options?.loader;
  }

  // ===========================================================================
  // Plugin Registration
  // ===========================================================================

  registerManifest(manifest: PluginManifest): void {
    this.checkNotInHook();

    if (this._plugins.has(manifest.pluginId)) {
      throw new DuplicateRegistrationError(manifest.pluginId);
    }

    if (!manifest.requiresSwitchboard.contains(SWITCHBOARD_VERSION)) {
      throw new CompatibilityError(
        manifest.pluginId,
        manifest.requiresSwitchboard.toString(),
        SWITCHBOARD_VERSION.toString(),
      );
    }

    for (const slotContrib of manifest.contributions.slots) {
      if (!this._slots.has(slotContrib.slotKey)) {
        throw new SlotNotFoundError(slotContrib.slotKey);
      }
    }

    for (const hookContrib of manifest.contributions.hooks) {
      if (!this._hooks.has(hookContrib.hookKey)) {
        throw new HookNotFoundError(hookContrib.hookKey);
      }
    }

    const lifecycle = new PluginLifecycle(manifest.pluginId);
    this._plugins.set(manifest.pluginId, { manifest, lifecycle });
  }

  unregister(pluginId: string): void {
    this.checkNotInHook();

    const entry = this._plugins.get(pluginId);
    if (!entry) {
      throw new PluginNotFoundError(pluginId);
    }

    if (entry.lifecycle.state === PluginState.ACTIVE) {
      throw new LifecycleError(pluginId, "unregister", entry.lifecycle.state);
    }

    // Remove contributions from slot registries
    for (const [slotKey, contributions] of this._slotContributions) {
      this._slotContributions.set(
        slotKey,
        contributions.filter((c) => c.pluginId !== pluginId),
      );
    }

    this._plugins.delete(pluginId);
  }

  // ===========================================================================
  // Plugin Lifecycle
  // ===========================================================================

  activate(pluginId: string): void {
    this.checkNotInHook();

    if (!this._plugins.has(pluginId)) {
      throw new PluginNotFoundError(pluginId);
    }

    this.activateInternal(pluginId);
  }

  deactivate(pluginId: string): void {
    this.checkNotInHook();

    const entry = this._plugins.get(pluginId);
    if (!entry) {
      throw new PluginNotFoundError(pluginId);
    }

    const { manifest, lifecycle } = entry;

    lifecycle.beginDeactivation();

    try {
      this.unregisterContributions(pluginId, manifest);

      const instance = lifecycle.instance as Record<string, unknown> | null;
      if (instance && typeof instance.deactivate === "function") {
        (instance.deactivate as (ctx: Record<string, unknown>) => void)({});
      }

      lifecycle.completeDeactivation();
    } catch (e) {
      lifecycle.fail(e instanceof Error ? e : new Error(String(e)));
      throw e;
    }
  }

  activationPlan(): ActivationPlan {
    return this.computeActivationPlan();
  }

  activateAll(): ActivationPlan {
    this.checkNotInHook();

    const plan = this.computeActivationPlan();

    const runtimeBlocked: Record<string, string> = { ...plan.blocked };
    const activated: string[] = [];

    for (const pluginId of plan.order) {
      if (pluginId in runtimeBlocked) continue;

      const entry = this._plugins.get(pluginId)!;
      let depFailed = false;
      for (const dep of entry.manifest.requires) {
        if (dep in runtimeBlocked) {
          runtimeBlocked[pluginId] = `dependency '${dep}' failed to activate`;
          depFailed = true;
          break;
        }
      }

      if (depFailed) continue;

      try {
        this.activateInternal(pluginId);
        activated.push(pluginId);
      } catch (e) {
        runtimeBlocked[pluginId] = `activation failed: ${e instanceof Error ? e.message : String(e)}`;
      }
    }

    return {
      order: activated,
      blocked: runtimeBlocked,
      cycles: plan.cycles,
    };
  }

  private activateInternal(pluginId: string): void {
    const entry = this._plugins.get(pluginId)!;
    const { manifest, lifecycle } = entry;

    if (!this._loader) {
      throw new Error("No loader configured - cannot activate plugins");
    }

    lifecycle.beginActivation();

    try {
      const pluginInstance = this._loader.loadEntrypoint(manifest.entrypoint);
      lifecycle.instance = pluginInstance;

      const instance = pluginInstance as Record<string, unknown>;
      if (typeof instance.activate === "function") {
        (instance.activate as (ctx: Record<string, unknown>) => void)({});
      }

      // Register slot contributions
      for (const slotContrib of manifest.contributions.slots) {
        const contribs = this._slotContributions.get(slotContrib.slotKey)!;
        contribs.push(slotContrib);
        contribs.sort((a, b) => {
          if (a.priority !== b.priority) return b.priority - a.priority;
          if (a.pluginId !== b.pluginId)
            return a.pluginId < b.pluginId ? -1 : 1;
          return a.contributionId < b.contributionId ? -1 : 1;
        });
      }

      // Register hook contributions
      for (const hookContrib of manifest.contributions.hooks) {
        const contribs = this._hookContributions.get(hookContrib.hookKey)!;
        contribs.push(hookContrib);
        contribs.sort((a, b) => {
          if (a.priority !== b.priority) return b.priority - a.priority;
          if (a.pluginId !== b.pluginId)
            return a.pluginId < b.pluginId ? -1 : 1;
          return a.contributionId < b.contributionId ? -1 : 1;
        });

        if (this._hookRouter && hookContrib.handler) {
          const handler = this._loader.loadCallable(hookContrib.handler);
          this._hookRouter.registerHandler(
            hookContrib.hookKey,
            hookContrib,
            handler,
          );
        }
      }

      lifecycle.completeActivation();
    } catch (e) {
      this.unregisterContributions(pluginId, manifest);
      lifecycle.rollback();
      throw e;
    }
  }

  private unregisterContributions(
    pluginId: string,
    manifest: PluginManifest,
  ): void {
    // Unregister hook handlers from router
    for (const hookContrib of manifest.contributions.hooks) {
      if (this._hookRouter) {
        this._hookRouter.unregisterHandler(
          hookContrib.hookKey,
          hookContrib.contributionId,
        );
      }
    }

    // Remove from local hook contribution tracking
    for (const [hookKey, contribs] of this._hookContributions) {
      this._hookContributions.set(
        hookKey,
        contribs.filter((c) => c.pluginId !== pluginId),
      );
    }

    // Remove slot contributions
    for (const [slotKey, contribs] of this._slotContributions) {
      this._slotContributions.set(
        slotKey,
        contribs.filter((c) => c.pluginId !== pluginId),
      );
    }
  }

  // ===========================================================================
  // Dependency Planning
  // ===========================================================================

  private computeActivationPlan(): ActivationPlan {
    const graph = new Map<string, Set<string>>();
    const blocked: Record<string, string> = {};
    const registered = new Set(this._plugins.keys());

    for (const [pluginId, { manifest, lifecycle }] of this._plugins) {
      if (lifecycle.state === PluginState.ACTIVE) continue;
      if (lifecycle.state === PluginState.FAILED) {
        blocked[pluginId] = "plugin in failed state";
        continue;
      }

      // Check hard dependencies
      const missingDeps: string[] = [];
      for (const dep of manifest.requires) {
        if (!registered.has(dep)) {
          missingDeps.push(dep);
        }
      }

      if (missingDeps.length > 0) {
        blocked[pluginId] = `missing dependencies: ${missingDeps.join(", ")}`;
        continue;
      }

      // Build dependency set
      const deps = new Set<string>();
      let isBlocked = false;

      for (const dep of manifest.requires) {
        const depEntry = this._plugins.get(dep)!;
        if (depEntry.lifecycle.state === PluginState.FAILED) {
          blocked[pluginId] = `dependency '${dep}' is in failed state`;
          isBlocked = true;
          break;
        }
        if (dep in blocked) {
          blocked[pluginId] = `dependency '${dep}' is blocked`;
          isBlocked = true;
          break;
        }
        deps.add(dep);
      }

      if (!isBlocked) {
        // Add optional deps for ordering
        for (const optDep of manifest.optionalRequires) {
          if (registered.has(optDep) && !(optDep in blocked)) {
            const optEntry = this._plugins.get(optDep)!;
            if (optEntry.lifecycle.state !== PluginState.FAILED) {
              deps.add(optDep);
            }
          }
        }
        graph.set(pluginId, deps);
      }
    }

    // Kahn's algorithm for topological sort
    const inDegree = new Map<string, number>();
    for (const [pluginId, deps] of graph) {
      let count = 0;
      for (const d of deps) {
        if (graph.has(d)) count++;
      }
      inDegree.set(pluginId, count);
    }

    const queue: string[] = [];
    for (const [p, d] of inDegree) {
      if (d === 0) queue.push(p);
    }
    queue.sort();

    const order: string[] = [];

    while (queue.length > 0) {
      const plugin = queue.shift()!;
      order.push(plugin);

      for (const [dependent, deps] of graph) {
        if (deps.has(plugin) && !order.includes(dependent)) {
          inDegree.set(dependent, inDegree.get(dependent)! - 1);
          if (inDegree.get(dependent) === 0 && !queue.includes(dependent)) {
            queue.push(dependent);
            queue.sort();
          }
        }
      }
    }

    // Any remaining nodes are in cycles
    const cycles: string[][] = [];
    const remaining = [...graph.keys()].filter((p) => !order.includes(p));
    if (remaining.length > 0) {
      cycles.push(...this.findCycles(graph, remaining));
      for (const pluginId of remaining) {
        blocked[pluginId] = "involved in dependency cycle";
      }
    }

    return { order, blocked, cycles };
  }

  private findCycles(
    graph: Map<string, Set<string>>,
    candidates: string[],
  ): string[][] {
    const cycles: string[][] = [];
    const visited = new Set<string>();

    const dfs = (node: string, path: string[], pathSet: Set<string>): void => {
      if (pathSet.has(node)) {
        const cycleStart = path.indexOf(node);
        const cycle = [...path.slice(cycleStart), node];
        // Check for duplicate cycles
        const cycleKey = cycle.join(",");
        if (!cycles.some((c) => c.join(",") === cycleKey)) {
          cycles.push(cycle);
        }
        return;
      }

      if (visited.has(node) || !graph.has(node)) return;

      visited.add(node);
      path.push(node);
      pathSet.add(node);

      const deps = [...(graph.get(node) ?? [])].sort();
      for (const dep of deps) {
        if (candidates.includes(dep) || pathSet.has(dep)) {
          dfs(dep, path, pathSet);
        }
      }

      path.pop();
      pathSet.delete(node);
    };

    for (const start of [...candidates].sort()) {
      if (!visited.has(start)) {
        dfs(start, [], new Set());
      }
    }

    return cycles;
  }

  // ===========================================================================
  // Resolution
  // ===========================================================================

  resolveSlot(
    slotKey: string,
    _context?: Record<string, unknown>,
  ): Contribution[] {
    if (!this._slots.has(slotKey)) {
      throw new SlotNotFoundError(slotKey);
    }

    const slotDef = this._slots.get(slotKey)!;
    const contributions = this._slotContributions.get(slotKey)!;

    // Filter to only active plugins
    const activeContributions = contributions.filter((c) => {
      const entry = this._plugins.get(c.pluginId);
      return entry && entry.lifecycle.state === PluginState.ACTIVE;
    });

    if (slotDef.policy === SlotPolicy.SINGLE && activeContributions.length > 0) {
      return [activeContributions[0]!];
    }

    return [...activeContributions];
  }

  // ===========================================================================
  // Hook Emission
  // ===========================================================================

  emit(
    hookKey: string,
    payload: Record<string, unknown>,
    context?: Record<string, unknown>,
  ): unknown[] | unknown | null {
    if (!this._hooks.has(hookKey)) {
      throw new HookNotFoundError(hookKey);
    }

    if (!this._hookRouter) {
      throw new Error("No hook router configured - cannot emit hooks");
    }

    const hookDef = this._hooks.get(hookKey)!;
    const policy = hookDef.effectivePolicy;

    this._inHookEmission = true;
    try {
      return this._hookRouter.emit(hookKey, policy, payload, context);
    } finally {
      this._inHookEmission = false;
    }
  }

  // ===========================================================================
  // Introspection
  // ===========================================================================

  runtimeInfo(): RuntimeInfo {
    let activePluginCount = 0;
    for (const { lifecycle } of this._plugins.values()) {
      if (lifecycle.state === PluginState.ACTIVE) {
        activePluginCount++;
      }
    }

    return {
      frameworkVersion: SWITCHBOARD_VERSION.toString(),
      platformVersion: getPlatformVersion(),
      pluginCount: this._plugins.size,
      activePluginCount,
      slotCount: this._slots.size,
      hookCount: this._hooks.size,
    };
  }

  snapshot(): RuntimeSnapshot {
    const timestamp = new Date().toISOString();
    const runtime = this.runtimeInfo();

    // Build plugin snapshots
    const pluginSnapshots: PluginSnapshot[] = [];
    const sortedPlugins = [...this._plugins.entries()].sort(([a], [b]) =>
      a < b ? -1 : 1,
    );

    for (const [pluginId, { manifest, lifecycle }] of sortedPlugins) {
      const contribIds: string[] = [];
      for (const sc of manifest.contributions.slots) {
        contribIds.push(sc.contributionId);
      }
      for (const hc of manifest.contributions.hooks) {
        contribIds.push(hc.contributionId);
      }

      pluginSnapshots.push({
        pluginId,
        version: manifest.pluginVersion.toString(),
        state: lifecycle.state,
        contributions: [...contribIds].sort(),
      });
    }

    // Build slot snapshots
    const slotSnapshots: SlotSnapshot[] = [];
    for (const slotKey of [...this._slots.keys()].sort()) {
      const slotDef = this._slots.get(slotKey)!;
      const contributions = this._slotContributions.get(slotKey)!;

      const activeContribs: ContributionSnapshot[] = contributions
        .filter((c) => {
          const entry = this._plugins.get(c.pluginId);
          return entry && entry.lifecycle.state === PluginState.ACTIVE;
        })
        .map((c) => ({
          contributionId: c.contributionId,
          pluginId: c.pluginId,
          priority: c.priority,
        }));

      slotSnapshots.push({
        slotKey,
        policy: slotDef.policy,
        contributions: activeContribs,
      });
    }

    // Build hook snapshots
    const hookSnapshots: HookSnapshot[] = [];
    for (const hookKey of [...this._hooks.keys()].sort()) {
      const hookDef = this._hooks.get(hookKey)!;
      const hookContribs = this._hookContributions.get(hookKey)!;

      const activeHandlers: ContributionSnapshot[] = hookContribs
        .filter((c) => {
          const entry = this._plugins.get(c.pluginId);
          return entry && entry.lifecycle.state === PluginState.ACTIVE;
        })
        .map((c) => ({
          contributionId: c.contributionId,
          pluginId: c.pluginId,
          priority: c.priority,
        }));

      hookSnapshots.push({
        hookKey,
        kind: hookDef.kind,
        policy: hookDef.effectivePolicy,
        handlers: activeHandlers,
      });
    }

    return {
      timestamp,
      runtime,
      plugins: pluginSnapshots,
      slots: slotSnapshots,
      hooks: hookSnapshots,
    };
  }

  dumpState(format: "text" | "json" = "text"): string {
    const snap = this.snapshot();
    if (format === "json") {
      return this.dumpJson(snap);
    }
    return this.dumpText(snap);
  }

  private dumpJson(snap: RuntimeSnapshot): string {
    const data = {
      hooks: snap.hooks.map((h) => ({
        handlers: h.handlers.map((c) => ({
          contribution_id: c.contributionId,
          plugin_id: c.pluginId,
          priority: c.priority,
        })),
        hook_key: h.hookKey,
        kind: h.kind,
        policy: h.policy,
      })),
      plugins: snap.plugins.map((p) => ({
        contributions: [...p.contributions],
        plugin_id: p.pluginId,
        state: p.state,
        version: p.version,
      })),
      runtime: {
        active_plugin_count: snap.runtime.activePluginCount,
        framework_version: snap.runtime.frameworkVersion,
        hook_count: snap.runtime.hookCount,
        platform_version: snap.runtime.platformVersion,
        plugin_count: snap.runtime.pluginCount,
        slot_count: snap.runtime.slotCount,
      },
      slots: snap.slots.map((s) => ({
        contributions: s.contributions.map((c) => ({
          contribution_id: c.contributionId,
          plugin_id: c.pluginId,
          priority: c.priority,
        })),
        policy: s.policy,
        slot_key: s.slotKey,
      })),
      timestamp: snap.timestamp,
    };
    return JSON.stringify(data, null, 2);
  }

  private dumpText(snap: RuntimeSnapshot): string {
    const lines: string[] = [];

    lines.push("=== Switchboard Runtime State ===");
    lines.push(`Timestamp: ${snap.timestamp}`);
    lines.push("");

    lines.push("Runtime:");
    lines.push(`  Framework: ${snap.runtime.frameworkVersion}`);
    lines.push(`  Platform: ${snap.runtime.platformVersion}`);
    lines.push(
      `  Plugins: ${snap.runtime.activePluginCount}/${snap.runtime.pluginCount} active`,
    );
    lines.push(`  Slots: ${snap.runtime.slotCount}`);
    lines.push(`  Hooks: ${snap.runtime.hookCount}`);
    lines.push("");

    lines.push("Plugins:");
    if (snap.plugins.length > 0) {
      for (const p of snap.plugins) {
        lines.push(`  ${p.pluginId} v${p.version} [${p.state}]`);
        if (p.contributions.length > 0) {
          lines.push(`    contributions: ${p.contributions.join(", ")}`);
        }
      }
    } else {
      lines.push("  (none)");
    }
    lines.push("");

    lines.push("Slots:");
    for (const s of snap.slots) {
      lines.push(`  ${s.slotKey} (${s.policy})`);
      if (s.contributions.length > 0) {
        for (const c of s.contributions) {
          lines.push(
            `    - ${c.contributionId} from ${c.pluginId} (pri=${c.priority})`,
          );
        }
      } else {
        lines.push("    (no contributions)");
      }
    }
    lines.push("");

    lines.push("Hooks:");
    for (const h of snap.hooks) {
      lines.push(`  ${h.hookKey} (${h.kind}, ${h.policy})`);
      if (h.handlers.length > 0) {
        for (const c of h.handlers) {
          lines.push(
            `    - ${c.contributionId} from ${c.pluginId} (pri=${c.priority})`,
          );
        }
      } else {
        lines.push("    (no handlers)");
      }
    }

    return lines.join("\n");
  }

  getPluginState(pluginId: string): PluginState {
    const entry = this._plugins.get(pluginId);
    if (!entry) {
      throw new PluginNotFoundError(pluginId);
    }
    return entry.lifecycle.state;
  }

  listPlugins(): string[] {
    return [...this._plugins.keys()];
  }

  listSlots(): string[] {
    return [...this._slots.keys()];
  }

  listHooks(): string[] {
    return [...this._hooks.keys()];
  }

  // ===========================================================================
  // Internal Helpers
  // ===========================================================================

  private checkNotInHook(): void {
    if (this._inHookEmission) {
      throw new LifecycleError(
        "PatchPanel",
        "mutate registry",
        "in_hook_emission",
      );
    }
  }
}
