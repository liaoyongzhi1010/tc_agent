/**
 * 主视图提供者 - Webview面板
 */

import * as vscode from 'vscode';
import { BackendManager } from '../services/BackendManager';
import { ApiClient } from '../services/ApiClient';
import { WorkspaceEditor } from '../services/WorkspaceEditor';

export class MainViewProvider implements vscode.WebviewViewProvider {
    private view?: vscode.WebviewView;
    private apiClient: ApiClient;
    private workspaceEditor: WorkspaceEditor;
    private currentMode: 'ask' | 'plan' | 'code' = 'ask';

    constructor(
        private context: vscode.ExtensionContext,
        private backendManager: BackendManager
    ) {
        this.apiClient = new ApiClient(backendManager);
        this.workspaceEditor = new WorkspaceEditor();
    }

    resolveWebviewView(webviewView: vscode.WebviewView): void {
        this.view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };

        webviewView.webview.html = this.getHtmlContent();

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
                case 'switchMode':
                    this.currentMode = message.mode;
                    break;
            }
        });
    }

    switchMode(mode: 'ask' | 'plan' | 'code'): void {
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

            const response = await this.apiClient.initPlan(task);
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
        }
    }

    private async handleConfirmPlan(workflowId: string): Promise<void> {
        try {
            await this.apiClient.confirmPlan(workflowId);
            this.view?.webview.postMessage({
                command: 'planConfirmed',
                workflowId
            });

            // 进入Code模式执行
            this.switchMode('code');
            // TODO: 启动WebSocket执行workflow
        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `确认计划失败: ${error}`
            });
        }
    }

    private getHtmlContent(): string {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TC Agent</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 10px;
            margin: 0;
        }
        .mode-tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 15px;
            border-bottom: 1px solid var(--vscode-panel-border);
            padding-bottom: 10px;
        }
        .mode-tab {
            padding: 6px 12px;
            border: none;
            background: transparent;
            color: var(--vscode-foreground);
            cursor: pointer;
            border-radius: 4px;
        }
        .mode-tab.active {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .mode-tab:hover:not(.active) {
            background: var(--vscode-toolbar-hoverBackground);
        }
        .input-area {
            margin-bottom: 15px;
        }
        textarea {
            width: 100%;
            min-height: 80px;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 4px;
            resize: vertical;
            box-sizing: border-box;
        }
        button.primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 16px;
            cursor: pointer;
            border-radius: 4px;
            margin-top: 8px;
        }
        button.primary:hover {
            background: var(--vscode-button-hoverBackground);
        }
        button.primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .response-area {
            margin-top: 15px;
            padding: 10px;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 4px;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
        }
        .step-list {
            list-style: none;
            padding: 0;
        }
        .step-item {
            padding: 8px;
            margin: 5px 0;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 4px;
            border-left: 3px solid var(--vscode-button-background);
        }
        .loading {
            display: none;
            color: var(--vscode-descriptionForeground);
            font-style: italic;
        }
        .loading.show {
            display: block;
        }
        .error {
            color: var(--vscode-errorForeground);
            padding: 8px;
            margin-top: 10px;
        }
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div class="mode-tabs">
        <button class="mode-tab active" data-mode="ask">Ask</button>
        <button class="mode-tab" data-mode="plan">Plan</button>
        <button class="mode-tab" data-mode="code">Code</button>
    </div>

    <!-- Ask Mode -->
    <div id="ask-mode" class="mode-content">
        <div class="input-area">
            <textarea id="ask-input" placeholder="输入您的问题，例如：OP-TEE如何实现HMAC操作？"></textarea>
            <button class="primary" id="ask-btn">提问</button>
        </div>
        <div class="loading" id="ask-loading">正在思考...</div>
        <div class="response-area hidden" id="ask-response"></div>
    </div>

    <!-- Plan Mode -->
    <div id="plan-mode" class="mode-content hidden">
        <div class="input-area">
            <textarea id="plan-input" placeholder="描述您的任务，例如：创建一个HMAC签名的TA"></textarea>
            <button class="primary" id="plan-btn">生成计划</button>
        </div>
        <div class="loading" id="plan-loading">正在生成计划...</div>
        <div id="plan-steps" class="hidden">
            <h4>执行计划</h4>
            <ul class="step-list" id="step-list"></ul>
            <div class="input-area">
                <textarea id="refine-input" placeholder="输入修改指令，例如：把第3步拆细"></textarea>
                <button class="primary" id="refine-btn">修改计划</button>
                <button class="primary" id="confirm-btn">确认执行</button>
            </div>
        </div>
    </div>

    <!-- Code Mode -->
    <div id="code-mode" class="mode-content hidden">
        <div class="response-area" id="code-output">
            等待执行计划...
        </div>
    </div>

    <div class="error hidden" id="error-msg"></div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentMode = 'ask';
        let currentWorkflowId = null;

        // 模式切换
        document.querySelectorAll('.mode-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                switchMode(tab.dataset.mode);
            });
        });

        function switchMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
            document.querySelector(\`[data-mode="\${mode}"]\`).classList.add('active');
            document.querySelectorAll('.mode-content').forEach(c => c.classList.add('hidden'));
            document.getElementById(\`\${mode}-mode\`).classList.remove('hidden');
        }

        // Ask
        document.getElementById('ask-btn').addEventListener('click', () => {
            const query = document.getElementById('ask-input').value.trim();
            if (query) {
                vscode.postMessage({ command: 'ask', query });
            }
        });

        // Plan
        document.getElementById('plan-btn').addEventListener('click', () => {
            const task = document.getElementById('plan-input').value.trim();
            if (task) {
                vscode.postMessage({ command: 'plan', task });
            }
        });

        document.getElementById('refine-btn').addEventListener('click', () => {
            const instruction = document.getElementById('refine-input').value.trim();
            if (instruction && currentWorkflowId) {
                vscode.postMessage({ command: 'refinePlan', workflowId: currentWorkflowId, instruction });
            }
        });

        document.getElementById('confirm-btn').addEventListener('click', () => {
            if (currentWorkflowId) {
                vscode.postMessage({ command: 'confirmPlan', workflowId: currentWorkflowId });
            }
        });

        // 消息处理
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'loading':
                    document.querySelectorAll('.loading').forEach(l => {
                        l.classList.toggle('show', message.loading);
                    });
                    break;
                case 'askResponse':
                    const responseEl = document.getElementById('ask-response');
                    responseEl.classList.remove('hidden');
                    responseEl.textContent = message.content;
                    break;
                case 'planResponse':
                    currentWorkflowId = message.workflowId;
                    const stepsEl = document.getElementById('plan-steps');
                    stepsEl.classList.remove('hidden');
                    const stepList = document.getElementById('step-list');
                    stepList.innerHTML = message.steps.map(s =>
                        \`<li class="step-item">\${s.id}. \${s.description}</li>\`
                    ).join('');
                    break;
                case 'planConfirmed':
                    switchMode('code');
                    break;
                case 'setMode':
                    switchMode(message.mode);
                    break;
                case 'error':
                    const errEl = document.getElementById('error-msg');
                    errEl.textContent = message.message;
                    errEl.classList.remove('hidden');
                    setTimeout(() => errEl.classList.add('hidden'), 5000);
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}
