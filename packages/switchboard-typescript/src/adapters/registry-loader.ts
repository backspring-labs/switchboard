import type { LoaderPort } from "../domain/ports.js";

export class RegistryLoader implements LoaderPort {
  private _entrypoints = new Map<string, () => unknown>();
  private _callables = new Map<string, (...args: unknown[]) => unknown>();

  registerEntrypoint(key: string, factory: () => unknown): void {
    this._entrypoints.set(key, factory);
  }

  registerCallable(key: string, callable: (...args: unknown[]) => unknown): void {
    this._callables.set(key, callable);
  }

  loadEntrypoint(entrypoint: string): unknown {
    const factory = this._entrypoints.get(entrypoint);
    if (!factory) {
      throw new Error(
        `Entrypoint not registered: '${entrypoint}'`,
      );
    }
    return factory();
  }

  loadCallable(importPath: string): (...args: unknown[]) => unknown {
    const callable = this._callables.get(importPath);
    if (!callable) {
      throw new Error(
        `Callable not registered: '${importPath}'`,
      );
    }
    return callable;
  }
}
