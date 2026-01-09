import * as vscode from 'vscode';

class Logger {
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('TC Agent');
  }

  info(message: string): void {
    this.log('INFO', message);
  }

  error(message: string, error?: any): void {
    this.log('ERROR', message);
    if (error) {
      this.log('ERROR', error.toString());
      if (error.stack) {
        this.log('ERROR', error.stack);
      }
    }
  }

  warn(message: string): void {
    this.log('WARN', message);
  }

  debug(message: string): void {
    this.log('DEBUG', message);
  }

  private log(level: string, message: string): void {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    this.outputChannel.appendLine(logMessage);
  }

  show(): void {
    this.outputChannel.show();
  }

  dispose(): void {
    this.outputChannel.dispose();
  }
}

export const logger = new Logger();
