import { HookPolicy } from "../domain/models.js";
import type { HookContribution } from "../domain/models.js";
import type { HookRouterPort } from "../domain/ports.js";

interface RegisteredHandler {
  contributionId: string;
  pluginId: string;
  priority: number;
  handler: (...args: unknown[]) => unknown;
}

export class MemoryHookRouter implements HookRouterPort {
  private _handlers = new Map<string, RegisteredHandler[]>();

  registerHandler(
    hookKey: string,
    contribution: HookContribution,
    handler: (...args: unknown[]) => unknown,
  ): void {
    if (!this._handlers.has(hookKey)) {
      this._handlers.set(hookKey, []);
    }

    const handlers = this._handlers.get(hookKey)!;
    handlers.push({
      contributionId: contribution.contributionId,
      pluginId: contribution.pluginId,
      priority: contribution.priority,
      handler,
    });

    // Sort by priority (descending), then plugin_id, then contribution_id
    handlers.sort((a, b) => {
      if (a.priority !== b.priority) return b.priority - a.priority;
      if (a.pluginId !== b.pluginId)
        return a.pluginId < b.pluginId ? -1 : 1;
      return a.contributionId < b.contributionId ? -1 : 1;
    });
  }

  unregisterHandler(hookKey: string, contributionId: string): void {
    const handlers = this._handlers.get(hookKey);
    if (!handlers) return;

    this._handlers.set(
      hookKey,
      handlers.filter((h) => h.contributionId !== contributionId),
    );
  }

  emit(
    hookKey: string,
    policy: HookPolicy,
    payload: Record<string, unknown>,
    context?: Record<string, unknown>,
  ): unknown[] | unknown | null {
    const handlers = this._handlers.get(hookKey) ?? [];

    if (handlers.length === 0) {
      return policy === HookPolicy.FIRST_RESULT ? null : [];
    }

    const ctx = context ?? {};

    if (policy === HookPolicy.BROADCAST) {
      return this.emitBroadcast(handlers, payload, ctx);
    }
    return this.emitFirstResult(handlers, payload, ctx);
  }

  private emitBroadcast(
    handlers: RegisteredHandler[],
    payload: Record<string, unknown>,
    context: Record<string, unknown>,
  ): unknown[] {
    const results: unknown[] = [];
    for (const registered of handlers) {
      try {
        const result = registered.handler(payload, context);
        results.push(result);
      } catch {
        // Continue to next handler (failure isolation)
      }
    }
    return results;
  }

  private emitFirstResult(
    handlers: RegisteredHandler[],
    payload: Record<string, unknown>,
    context: Record<string, unknown>,
  ): unknown | null {
    for (const registered of handlers) {
      const result = registered.handler(payload, context);
      if (result !== null && result !== undefined) {
        return result;
      }
    }
    return null;
  }

  clear(): void {
    this._handlers.clear();
  }
}
