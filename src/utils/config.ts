import * as vscode from 'vscode';

export class Config {
  private static readonly SECTION = 'tcAgent';

  static get serverUrl(): string {
    return this.getConfig<string>('serverUrl', 'http://localhost:8000');
  }

  static get wsUrl(): string {
    return this.getConfig<string>('wsUrl', 'ws://localhost:8000/ws');
  }

  static get defaultMode(): 'ask' | 'plan' | 'code' {
    return this.getConfig<'ask' | 'plan' | 'code'>('defaultMode', 'ask');
  }

  private static getConfig<T>(key: string, defaultValue: T): T {
    const config = vscode.workspace.getConfiguration(this.SECTION);
    return config.get<T>(key, defaultValue);
  }

  static async update(key: string, value: any): Promise<void> {
    const config = vscode.workspace.getConfiguration(this.SECTION);
    await config.update(key, value, vscode.ConfigurationTarget.Global);
  }
}
