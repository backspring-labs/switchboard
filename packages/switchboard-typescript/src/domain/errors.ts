export class SwitchboardError extends Error {
  constructor(message: string) {
    super(message);
    this.name = this.constructor.name;
  }
}

export class PluginNotFoundError extends SwitchboardError {
  constructor(public readonly pluginId: string) {
    super(`Plugin not found: ${pluginId}`);
  }
}

export class SlotNotFoundError extends SwitchboardError {
  constructor(public readonly slotKey: string) {
    super(`Slot not found: ${slotKey}`);
  }
}

export class HookNotFoundError extends SwitchboardError {
  constructor(public readonly hookKey: string) {
    super(`Hook not found: ${hookKey}`);
  }
}

export class CompatibilityError extends SwitchboardError {
  constructor(
    public readonly pluginId: string,
    public readonly required: string,
    public readonly current: string,
  ) {
    super(
      `Plugin ${pluginId} requires switchboard ${required}, but ${current} is installed`,
    );
  }
}

export class LifecycleError extends SwitchboardError {
  constructor(
    public readonly pluginId: string,
    public readonly operation: string,
    public readonly currentState: string,
  ) {
    super(
      `Cannot ${operation} plugin ${pluginId}: currently in state '${currentState}'`,
    );
  }
}

export class DuplicateRegistrationError extends SwitchboardError {
  constructor(public readonly pluginId: string) {
    super(`Plugin already registered: ${pluginId}`);
  }
}

export class ManifestError extends SwitchboardError {
  public readonly pluginId: string | undefined;

  constructor(message: string, pluginId?: string) {
    const prefix = pluginId ? `Plugin ${pluginId}: ` : "";
    super(`${prefix}${message}`);
    this.pluginId = pluginId;
  }
}

export class ContributionError extends SwitchboardError {
  public readonly contributionId: string | undefined;

  constructor(message: string, contributionId?: string) {
    const prefix = contributionId
      ? `Contribution ${contributionId}: `
      : "";
    super(`${prefix}${message}`);
    this.contributionId = contributionId;
  }
}
