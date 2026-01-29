/**
 * Python后端进程管理器
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
export class BackendManager {
    private process: cp.ChildProcess | null = null;
    private port: number;
    private ready: boolean = false;
    private outputChannel: vscode.OutputChannel;

    constructor(private context: vscode.ExtensionContext) {
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

    private getBackendEnv(): NodeJS.ProcessEnv {
        const config = vscode.workspace.getConfiguration('tcAgent');
        const env: NodeJS.ProcessEnv = {
            ...process.env,
            PYTHONUNBUFFERED: '1',
            TC_AGENT_LLM_PROVIDER: config.get<string>('llm.provider') || 'qwen',
        };

        // 传递API Keys
        const qwenKey = config.get<string>('llm.qwenApiKey');
        if (qwenKey) {
            env.TC_AGENT_QWEN_API_KEY = qwenKey;
        }

        const zhipuKey = config.get<string>('llm.zhipuApiKey');
        if (zhipuKey) {
            env.TC_AGENT_ZHIPU_API_KEY = zhipuKey;
        }

        const doubaoKey = config.get<string>('llm.doubaoApiKey');
        if (doubaoKey) {
            env.TC_AGENT_DOUBAO_API_KEY = doubaoKey;
        }

        const doubaoEndpoint = config.get<string>('llm.doubaoEndpointId');
        if (doubaoEndpoint) {
            env.TC_AGENT_DOUBAO_ENDPOINT_ID = doubaoEndpoint;
        }

        const llmModel = config.get<string>('llm.model');
        if (llmModel) {
            env.TC_AGENT_LLM_MODEL = llmModel;
        }

        const embeddingMode = config.get<string>('embedding.mode');
        if (embeddingMode) {
            env.TC_AGENT_EMBEDDING_MODE = embeddingMode;
        }

        return env;
    }

    async start(): Promise<void> {
        if (this.ready) {
            console.log('Backend already running');
            return;
        }

        const pythonPath = this.getPythonPath();
        const backendPath = path.join(this.context.extensionPath, '..', 'backend');

        return new Promise((resolve, reject) => {
            this.outputChannel.appendLine(`Starting backend with Python: ${pythonPath}`);
            this.outputChannel.appendLine(`Backend path: ${backendPath}`);

            this.process = cp.spawn(
                pythonPath,
                ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(this.port)],
                {
                    cwd: backendPath,
                    env: this.getBackendEnv()
                }
            );

            this.process.stdout?.on('data', (data) => {
                const output = data.toString();
                this.outputChannel.appendLine(output);

                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    this.ready = true;
                    resolve();
                }
            });

            this.process.stderr?.on('data', (data) => {
                const output = data.toString();
                this.outputChannel.appendLine(`[stderr] ${output}`);

                // uvicorn 的启动信息可能在 stderr
                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    this.ready = true;
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
}
