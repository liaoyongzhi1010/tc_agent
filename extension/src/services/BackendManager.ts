/**
 * Python后端进程管理器
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { EventEmitter } from 'events';

export class BackendManager extends EventEmitter {
    private process: cp.ChildProcess | null = null;
    private port: number;
    private ready: boolean = false;
    private outputChannel: vscode.OutputChannel;

    constructor(private context: vscode.ExtensionContext) {
        super();
        this.outputChannel = vscode.window.createOutputChannel('TC Agent Backend');
        this.port = this.getPort();
    }

    private getPort(): number {
        const config = vscode.workspace.getConfiguration('tcAgent');
        return config.get<number>('backendPort') || 8765;
    }

    private getPythonPath(): string {
        const config = vscode.workspace.getConfiguration('tcAgent');
        return config.get<string>('pythonPath') || 'python3';
    }

    async start(): Promise<void> {
        if (this.ready) {
            console.log('Backend already running');
            return;
        }

        const pythonPath = this.getPythonPath();
        const backendPath = path.join(this.context.extensionPath, 'backend');

        return new Promise((resolve, reject) => {
            this.outputChannel.appendLine(`Starting backend with Python: ${pythonPath}`);
            this.outputChannel.appendLine(`Backend path: ${backendPath}`);

            this.process = cp.spawn(
                pythonPath,
                ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(this.port)],
                {
                    cwd: backendPath,
                    env: { ...process.env, PYTHONUNBUFFERED: '1' }
                }
            );

            this.process.stdout?.on('data', (data) => {
                const output = data.toString();
                this.outputChannel.appendLine(output);

                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    this.ready = true;
                    this.emit('ready');
                    resolve();
                }
            });

            this.process.stderr?.on('data', (data) => {
                const output = data.toString();
                this.outputChannel.appendLine(`[stderr] ${output}`);

                // uvicorn 的启动信息可能在 stderr
                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    this.ready = true;
                    this.emit('ready');
                    resolve();
                }
            });

            this.process.on('error', (error) => {
                this.outputChannel.appendLine(`Process error: ${error.message}`);
                reject(error);
            });

            this.process.on('exit', (code) => {
                this.ready = false;
                this.outputChannel.appendLine(`Backend exited with code: ${code}`);
                this.emit('exit', code);
            });

            // 超时处理
            setTimeout(() => {
                if (!this.ready) {
                    reject(new Error('Backend startup timeout'));
                }
            }, 30000);
        });
    }

    stop(): void {
        if (this.process) {
            this.process.kill();
            this.process = null;
            this.ready = false;
            this.outputChannel.appendLine('Backend stopped');
        }
    }

    isReady(): boolean {
        return this.ready;
    }

    getBaseUrl(): string {
        return `http://127.0.0.1:${this.port}`;
    }

    showOutput(): void {
        this.outputChannel.show();
    }
}
