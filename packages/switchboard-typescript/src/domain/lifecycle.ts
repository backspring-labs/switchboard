import { LifecycleError } from "./errors.js";

export const PluginState = {
  READY: "ready",
  STARTING: "starting",
  ACTIVE: "active",
  STOPPING: "stopping",
  FAILED: "failed",
} as const;
export type PluginState = (typeof PluginState)[keyof typeof PluginState];

const TRANSITIONS: Record<string, Record<string, PluginState>> = {
  ready: { begin_activation: PluginState.STARTING },
  starting: {
    complete_activation: PluginState.ACTIVE,
    fail: PluginState.FAILED,
    rollback: PluginState.READY,
  },
  active: {
    begin_deactivation: PluginState.STOPPING,
    fail: PluginState.FAILED,
  },
  stopping: { complete_deactivation: PluginState.READY },
  failed: { reset: PluginState.READY },
};

export class PluginLifecycle {
  readonly pluginId: string;
  private _state: PluginState = PluginState.READY;
  private _instance: unknown = null;
  private _lastError: Error | null = null;

  constructor(pluginId: string) {
    this.pluginId = pluginId;
  }

  get state(): PluginState {
    return this._state;
  }

  get instance(): unknown {
    return this._instance;
  }

  set instance(value: unknown) {
    this._instance = value;
  }

  get lastError(): Error | null {
    return this._lastError;
  }

  get isActive(): boolean {
    return this._state === PluginState.ACTIVE;
  }

  get isFailed(): boolean {
    return this._state === PluginState.FAILED;
  }

  private transition(trigger: string, operation: string): void {
    const stateTransitions = TRANSITIONS[this._state];
    const dest = stateTransitions?.[trigger];
    if (dest === undefined) {
      throw new LifecycleError(this.pluginId, operation, this._state);
    }
    this._state = dest;
  }

  beginActivation(): void {
    this.transition("begin_activation", "activate");
  }

  completeActivation(): void {
    this.transition("complete_activation", "complete activation");
  }

  beginDeactivation(): void {
    this.transition("begin_deactivation", "deactivate");
  }

  completeDeactivation(): void {
    this._instance = null;
    this.transition("complete_deactivation", "complete deactivation");
  }

  fail(error: Error): void {
    this._lastError = error;
    this._instance = null;
    this.transition("fail", "fail");
  }

  rollback(): void {
    this._instance = null;
    this.transition("rollback", "rollback");
  }

  reset(): void {
    this._lastError = null;
    this.transition("reset", "reset");
  }
}
