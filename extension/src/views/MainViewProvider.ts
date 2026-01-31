/**
 * 主视图提供者 - Webview面板
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { TextDecoder } from 'util';
import { BackendManager } from '../services/BackendManager';
import { ApiClient, WorkspaceFile } from '../services/ApiClient';
import { getMainViewHtml } from './webview/mainViewHtml';

export class MainViewProvider implements vscode.WebviewViewProvider {
    private view?: vscode.WebviewView;
    private apiClient: ApiClient;
    private currentMode: 'ask' | 'agent' = 'ask';
    private codeWebSocket: WebSocket | null = null;
    private cancelRequested = false;
    private workspaceId?: string;

    constructor(
        private context: vscode.ExtensionContext,
        private backendManager: BackendManager
    ) {
        this.apiClient = new ApiClient(backendManager);
    }

    private getWorkspaceRoot(): string | undefined {
        const folders = vscode.workspace.workspaceFolders;
        return folders && folders.length > 0 ? folders[0].uri.fsPath : undefined;
    }

    resolveWebviewView(webviewView: vscode.WebviewView): void {
        this.view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };

        webviewView.webview.html = this.getHtmlContent(webviewView.webview);

        // 处理来自webview的消息
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'ask':
                    await this.handleAsk(message.query);
                    break;
                case 'plan':
                    await this.handlePlan(message.task);
                    break;
                case 'refinePlan':
                    await this.handleRefinePlan(message.workflowId, message.instruction);
                    break;
                case 'confirmPlan':
                    await this.handleConfirmPlan(message.workflowId);
                    break;
                case 'cancelCode':
                    await this.handleCancelCode();
                    break;
                case 'switchMode':
                    this.currentMode = message.mode;
                    break;
                case 'switchModel':
                    const config = vscode.workspace.getConfiguration('tcAgent');
                    await config.update('llm.provider', message.model, true);
                    vscode.window.showInformationMessage(`已切换到 ${message.model} 模型`);
                    break;
            }
        });
    }

    switchMode(mode: 'ask' | 'agent'): void {
        this.currentMode = mode;
        this.view?.webview.postMessage({ command: 'setMode', mode });
    }

    private async handleAsk(query: string): Promise<void> {
        try {
            this.view?.webview.postMessage({ command: 'loading', loading: true });

            let fullResponse = '';
            for await (const event of this.apiClient.askStream({ query })) {
                if (event.type === 'content') {
                    fullResponse += event.data;
                    this.view?.webview.postMessage({
                        command: 'askResponse',
                        content: fullResponse,
                        streaming: true
                    });
                } else if (event.type === 'sources') {
                    this.view?.webview.postMessage({
                        command: 'sources',
                        sources: event.data
                    });
                } else if (event.type === 'status') {
                    this.view?.webview.postMessage({
                        command: 'status',
                        status: event.data
                    });
                }
            }

            this.view?.webview.postMessage({
                command: 'askResponse',
                content: fullResponse,
                streaming: false
            });
        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `请求失败: ${error}`
            });
        } finally {
            this.view?.webview.postMessage({ command: 'loading', loading: false });
        }
    }

    private async handlePlan(task: string): Promise<void> {
        try {
            this.view?.webview.postMessage({ command: 'loading', loading: true });

            const workspaceRoot = this.getWorkspaceRoot();
            if (!workspaceRoot) {
                vscode.window.showErrorMessage('请先打开一个工作区文件夹，再使用 Agent 模式');
                return;
            }

            const workspaceId = await this.ensureWorkspaceReady();
            const response = await this.apiClient.initPlan(task, workspaceRoot, workspaceId);
            this.view?.webview.postMessage({
                command: 'planResponse',
                workflowId: response.workflow_id,
                steps: response.steps
            });
        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `创建计划失败: ${error}`
            });
        } finally {
            this.view?.webview.postMessage({ command: 'loading', loading: false });
        }
    }

    private async handleRefinePlan(workflowId: string, instruction: string): Promise<void> {
        try {
            this.view?.webview.postMessage({ command: 'loading', loading: true });
            const response = await this.apiClient.refinePlan(workflowId, instruction);
            this.view?.webview.postMessage({
                command: 'planResponse',
                workflowId: response.workflow_id,
                steps: response.steps
            });
        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `修改计划失败: ${error}`
            });
        } finally {
            this.view?.webview.postMessage({ command: 'loading', loading: false });
        }
    }

    private async handleConfirmPlan(workflowId: string): Promise<void> {
        try {
            await this.apiClient.confirmPlan(workflowId);
            this.view?.webview.postMessage({
                command: 'planConfirmed',
                workflowId
            });

            // Agent模式确认后直接执行
            await this.handleExecuteWorkflow(workflowId);
        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `确认计划失败: ${error}`
            });
        }
    }

    private async handleExecuteWorkflow(workflowId: string): Promise<void> {
        // 关闭旧连接
        if (this.codeWebSocket) {
            this.codeWebSocket.close();
        }

        try {
            this.cancelRequested = false;
            this.view?.webview.postMessage({ command: 'codeStart' });

            const ws = this.apiClient.createCodeWebSocket(workflowId);
            this.codeWebSocket = ws;

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleAgentEvent(data);
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e);
                }
            };

            ws.onerror = (error) => {
                this.view?.webview.postMessage({
                    command: 'error',
                    message: `WebSocket错误: ${error}`
                });
            };

            ws.onclose = () => {
                this.codeWebSocket = null;
                this.view?.webview.postMessage({ command: 'codeComplete' });
            };

        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `执行失败: ${error}`
            });
        }
    }


    private handleAgentEvent(event: { type: string; data?: any }): void {
        switch (event.type) {
            case 'cancelled':
                this.view?.webview.postMessage({
                    command: 'codeCancelled',
                    message: event.data?.message || '已取消'
                });
                break;

            case 'step_start':
                this.view?.webview.postMessage({
                    command: 'stepStart',
                    stepIndex: event.data?.step_index,
                    step: event.data?.step
                });
                break;

            case 'thought':
                this.view?.webview.postMessage({
                    command: 'thought',
                    content: event.data?.content
                });
                break;

            case 'action':
                this.view?.webview.postMessage({
                    command: 'action',
                    tool: event.data?.tool,
                    input: event.data?.input
                });
                break;

            case 'file_ops':
                void this.applyFileOps(event.data?.ops || []);
                break;
            case 'file_read_request':
                void this.handleFileReadRequest(event.data);
                break;

            case 'observation':
                this.view?.webview.postMessage({
                    command: 'observation',
                    content: event.data?.content,
                    success: event.data?.success,
                    tool: event.data?.tool
                });
                break;

            case 'step_complete':
                this.view?.webview.postMessage({
                    command: 'stepComplete',
                    stepIndex: event.data?.step_index
                });
                break;

            case 'complete':
            case 'workflow_complete':
                this.view?.webview.postMessage({
                    command: 'codeResult',
                    answer: event.data?.answer || event.data?.message
                });
                break;

            case 'error':
                this.view?.webview.postMessage({
                    command: 'error',
                    message: event.data?.message || String(event.data)
                });
                break;
        }
    }

    private async handleCancelCode(): Promise<void> {
        this.cancelRequested = true;
        this.view?.webview.postMessage({ command: 'codeCancelRequested' });

        if (this.codeWebSocket && this.codeWebSocket.readyState === WebSocket.OPEN) {
            this.codeWebSocket.send(JSON.stringify({ type: 'cancel' }));
            return;
        }

    }

    private async openFile(path: string): Promise<void> {
        const uri = vscode.Uri.file(path);
        const document = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(document);
    }

    private async ensureWorkspaceReady(): Promise<string> {
        if (this.workspaceId) {
            return this.workspaceId;
        }

        const workspaceRoot = this.getWorkspaceRoot();
        if (!workspaceRoot) {
            throw new Error('未打开工作区');
        }

        const init = await this.apiClient.initWorkspace();
        this.workspaceId = init.workspace_id;

        await this.syncWorkspaceSnapshot();

        return this.workspaceId;
    }

    private async syncWorkspaceSnapshot(): Promise<void> {
        const workspaceRoot = this.getWorkspaceRoot();
        if (!workspaceRoot || !this.workspaceId) {
            return;
        }

        const rootUri = vscode.Uri.file(workspaceRoot);
        const include = new vscode.RelativePattern(rootUri, '**/*');
        const exclude = '**/{.git,node_modules,dist,build,out,.venv,.DS_Store}/**';
        const files = await vscode.workspace.findFiles(include, exclude);

        const batch: WorkspaceFile[] = [];
        const maxSize = 1024 * 1024;
        const batchSize = 40;

        for (const uri of files) {
            try {
                const stat = await vscode.workspace.fs.stat(uri);
                if (stat.size > maxSize) {
                    continue;
                }
                const bytes = await vscode.workspace.fs.readFile(uri);
                const content = new TextDecoder('utf-8').decode(bytes);
                const rel = path.relative(workspaceRoot, uri.fsPath);
                if (!rel || rel.startsWith('..')) {
                    continue;
                }
                batch.push({ path: rel, content, encoding: 'utf-8' });
                if (batch.length >= batchSize) {
                    await this.apiClient.syncWorkspace(this.workspaceId, batch.splice(0, batch.length));
                }
            } catch {
                // ignore unreadable files
            }
        }

        if (batch.length > 0) {
            await this.apiClient.syncWorkspace(this.workspaceId, batch.splice(0, batch.length));
        }
    }

    private isInWorkspace(filePath: string): boolean {
        const root = this.getWorkspaceRoot();
        if (!root) {
            return false;
        }
        const rel = path.relative(root, filePath);
        if (rel === '') {
            return true;
        }
        return !rel.startsWith('..') && !path.isAbsolute(rel);
    }

    private async handleFileReadRequest(data: { request_id?: string; path?: string; encoding?: string }): Promise<void> {
        const requestId = data?.request_id;
        const reqPath = data?.path;
        if (!requestId || !reqPath) {
            return;
        }

        const workspaceRoot = this.getWorkspaceRoot();
        let filePath = reqPath;
        if (!path.isAbsolute(filePath)) {
            if (!workspaceRoot) {
                this.codeWebSocket?.send(
                    JSON.stringify({
                        type: 'file_read_response',
                        data: { request_id: requestId, ok: false, error: '未打开工作区' }
                    })
                );
                return;
            }
            filePath = path.join(workspaceRoot, filePath);
        } else if (!this.isInWorkspace(filePath)) {
            this.codeWebSocket?.send(
                JSON.stringify({
                    type: 'file_read_response',
                    data: { request_id: requestId, ok: false, error: '禁止读取工作区外文件' }
                })
            );
            return;
        }

        try {
            const bytes = await vscode.workspace.fs.readFile(vscode.Uri.file(filePath));
            const decoder = new TextDecoder('utf-8');
            const content = decoder.decode(bytes);
            this.codeWebSocket?.send(
                JSON.stringify({
                    type: 'file_read_response',
                    data: { request_id: requestId, ok: true, content }
                })
            );
        } catch (error) {
            this.codeWebSocket?.send(
                JSON.stringify({
                    type: 'file_read_response',
                    data: { request_id: requestId, ok: false, error: String(error) }
                })
            );
        }
    }

    private async applyFileOps(ops: Array<{ path: string; content?: string; encoding?: string; create_dirs?: boolean }>): Promise<void> {
        if (!Array.isArray(ops) || ops.length === 0) {
            return;
        }

        const workspaceRoot = this.getWorkspaceRoot();
        let wrote = 0;
        let firstFile: string | undefined;

        const syncFiles: WorkspaceFile[] = [];
        for (const op of ops) {
            if (!op?.path) {
                continue;
            }

            let filePath = op.path;
            if (!path.isAbsolute(filePath)) {
                if (!workspaceRoot) {
                    vscode.window.showErrorMessage(`无法写入文件(未打开工作区): ${filePath}`);
                    continue;
                }
                filePath = path.join(workspaceRoot, filePath);
            } else if (!this.isInWorkspace(filePath)) {
                vscode.window.showErrorMessage(`禁止写入工作区外文件: ${filePath}`);
                continue;
            }

            if (op.create_dirs !== false) {
                const dirPath = path.dirname(filePath);
                await vscode.workspace.fs.createDirectory(vscode.Uri.file(dirPath));
            }

            const encoding = (op.encoding || 'utf-8').toLowerCase();
            if (encoding !== 'utf-8' && encoding !== 'utf8') {
                vscode.window.showWarningMessage(`暂不支持编码 ${op.encoding}，已按 utf-8 写入: ${filePath}`);
            }

            const content = typeof op.content === 'string' ? op.content : '';
            await vscode.workspace.fs.writeFile(
                vscode.Uri.file(filePath),
                new TextEncoder().encode(content)
            );

            if (this.workspaceId && this.isInWorkspace(filePath)) {
                const rel = path.relative(workspaceRoot || '', filePath);
                syncFiles.push({ path: rel, content, encoding: op.encoding || 'utf-8' });
            }

            if (!firstFile) {
                firstFile = filePath;
            }
            wrote += 1;
        }

        if (this.workspaceId && syncFiles.length > 0) {
            await this.apiClient.syncWorkspace(this.workspaceId, syncFiles);
        }

        if (wrote > 0) {
            const action = await vscode.window.showInformationMessage(
                `已写入 ${wrote} 个文件`,
                '打开第一个'
            );
            if (action === '打开第一个' && firstFile) {
                await this.openFile(firstFile);
            }
        }
    }

    private getHtmlContent(webview: vscode.Webview): string {
        return getMainViewHtml(webview, this.context.extensionUri);
    }
}
