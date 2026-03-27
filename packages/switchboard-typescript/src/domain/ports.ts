import type { HookContribution, HookPolicy } from "./models.js";

export interface HookRouterPort {
  registerHandler(
    hookKey: string,
    contribution: HookContribution,
    handler: (...args: unknown[]) => unknown,
  ): void;

  unregisterHandler(hookKey: string, contributionId: string): void;

  emit(
    hookKey: string,
    policy: HookPolicy,
    payload: Record<string, unknown>,
    context?: Record<string, unknown>,
  ): unknown[] | unknown | null;

  clear(): void;
}

export interface LoaderPort {
  loadEntrypoint(entrypoint: string): unknown;
  loadCallable(importPath: string): (...args: unknown[]) => unknown;
}
