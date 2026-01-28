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
    private currentWorkflowId: string | null = null;
    private codeWebSocket: WebSocket | null = null;

    constructor(
        private context: vscode.ExtensionContext,
        private backendManager: BackendManager
    ) {
        this.apiClient = new ApiClient(backendManager);
        this.workspaceEditor = new WorkspaceEditor();
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
                case 'executeWorkflow':
                    await this.handleExecuteWorkflow(message.workflowId);
                    break;
                case 'directExecute':
                    await this.handleDirectExecute(message.task);
                    break;
                case 'switchMode':
                    this.currentMode = message.mode;
                    break;
                case 'switchModel':
                    const config = vscode.workspace.getConfiguration('tcAgent');
                    await config.update('llm.provider', message.model, true);
                    vscode.window.showInformationMessage(`已切换到 ${message.model} 模型`);
                    break;
                case 'applyFileEdit':
                    await this.handleApplyFileEdit(message.path, message.content);
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

            const response = await this.apiClient.initPlan(task, this.getWorkspaceRoot());
            this.currentWorkflowId = response.workflow_id;
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
            this.currentWorkflowId = workflowId;
            this.view?.webview.postMessage({
                command: 'planConfirmed',
                workflowId
            });

            // 自动切换到Code模式并开始执行
            this.switchMode('code');
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
                this.view?.webview.postMessage({ command: 'codeComplete' });
            };

        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `执行失败: ${error}`
            });
        }
    }

    private async handleDirectExecute(task: string): Promise<void> {
        try {
            this.view?.webview.postMessage({ command: 'codeStart' });

            for await (const event of this.apiClient.executeDirectStream(task, this.getWorkspaceRoot())) {
                this.handleAgentEvent(event);
            }

            this.view?.webview.postMessage({ command: 'codeComplete' });
        } catch (error) {
            this.view?.webview.postMessage({
                command: 'error',
                message: `执行失败: ${error}`
            });
        }
    }

    private handleAgentEvent(event: { type: string; data?: any }): void {
        switch (event.type) {
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

            case 'observation':
                const content = event.data?.content;
                this.view?.webview.postMessage({
                    command: 'observation',
                    content: content
                });
                // 检查是否是文件操作
                this.checkFileOperation(content);
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

    private async checkFileOperation(content: string): Promise<void> {
        // 检测file_write操作结果
        if (typeof content === 'string' && content.includes('path') && content.includes('写入成功')) {
            try {
                // 尝试解析文件路径
                const pathMatch = content.match(/path['":\s]+([^'"\s,}]+)/);
                if (pathMatch) {
                    const filePath = pathMatch[1];
                    // 通知用户文件已创建
                    const action = await vscode.window.showInformationMessage(
                        `文件已创建: ${filePath}`,
                        '打开文件'
                    );
                    if (action === '打开文件') {
                        await this.workspaceEditor.openFile(filePath);
                    }
                }
            } catch (e) {
                console.error('Failed to parse file operation:', e);
            }
        }
    }

    private async handleApplyFileEdit(path: string, content: string): Promise<void> {
        try {
            await this.workspaceEditor.createFile(path, content);
            await this.workspaceEditor.openFile(path);
            vscode.window.showInformationMessage(`文件已创建: ${path}`);
        } catch (error) {
            vscode.window.showErrorMessage(`创建文件失败: ${error}`);
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
        * { box-sizing: border-box; }
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            display: flex;
            flex-direction: column;
        }

        /* 聊天区域 */
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }

        /* 消息样式 */
        .message {
            margin-bottom: 16px;
            max-width: 100%;
        }

        .message-user {
            display: flex;
            justify-content: flex-end;
        }

        .message-user .message-content {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            padding: 10px 14px;
            border-radius: 18px 18px 4px 18px;
            max-width: 85%;
        }

        .message-assistant {
            display: flex;
            flex-direction: column;
        }

        .message-assistant .message-content {
            background: transparent;
            padding: 0;
            line-height: 1.6;
        }

        /* 可折叠的来源区域 */
        .sources-collapse {
            margin-bottom: 12px;
        }

        .sources-collapse summary {
            cursor: pointer;
            padding: 8px 12px;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 6px;
            font-size: 13px;
            color: var(--vscode-descriptionForeground);
            list-style: none;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .sources-collapse summary::-webkit-details-marker {
            display: none;
        }

        .sources-collapse summary::before {
            content: '▶';
            font-size: 10px;
            transition: transform 0.2s;
        }

        .sources-collapse[open] summary::before {
            transform: rotate(90deg);
        }

        .sources-collapse .sources-content {
            padding: 10px 12px;
            margin-top: 4px;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 6px;
            font-size: 12px;
        }

        .source-item {
            padding: 4px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .source-item::before {
            content: '•';
            color: var(--vscode-descriptionForeground);
        }

        /* Markdown 渲染 */
        .markdown-content {
            line-height: 1.6;
        }

        .markdown-content h1, .markdown-content h2, .markdown-content h3, .markdown-content h4 {
            margin: 16px 0 8px 0;
            font-weight: 600;
        }

        .markdown-content h1 { font-size: 1.5em; }
        .markdown-content h2 { font-size: 1.3em; }
        .markdown-content h3 { font-size: 1.1em; }

        .markdown-content p {
            margin: 8px 0;
        }

        .markdown-content ul, .markdown-content ol {
            margin: 8px 0;
            padding-left: 24px;
        }

        .markdown-content li {
            margin: 4px 0;
        }

        .markdown-content code {
            font-family: var(--vscode-editor-font-family);
            font-size: 12px;
        }

        .markdown-content strong {
            font-weight: 600;
        }

        /* Plan 步骤 */
        .plan-steps {
            margin: 12px 0;
        }

        .step-item {
            padding: 10px 12px;
            margin: 6px 0;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 6px;
            border-left: 3px solid var(--vscode-button-background);
        }

        .step-item.active {
            border-left-color: #4CAF50;
            background: rgba(76, 175, 80, 0.1);
        }

        .step-item.completed {
            border-left-color: #888;
            opacity: 0.7;
        }

        .plan-actions {
            margin-top: 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .plan-actions textarea {
            width: 100%;
            min-height: 40px;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 6px;
            resize: none;
            font-family: inherit;
            margin-bottom: 8px;
        }

        /* Agent 事件 */
        .agent-event {
            margin: 8px 0;
            padding: 10px 12px;
            border-radius: 6px;
            font-size: 13px;
        }

        .event-thought {
            border-left: 3px solid #2196F3;
            background: rgba(33, 150, 243, 0.08);
        }

        .event-action {
            border-left: 3px solid #4CAF50;
            background: rgba(76, 175, 80, 0.08);
        }

        .event-observation {
            border-left: 3px solid #9E9E9E;
            background: rgba(158, 158, 158, 0.08);
            font-family: var(--vscode-editor-font-family);
            font-size: 12px;
            white-space: pre-wrap;
            max-height: 200px;
            overflow-y: auto;
        }

        .event-label {
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 6px;
            opacity: 0.8;
        }

        /* 进度条 */
        .progress-bar {
            height: 3px;
            background: var(--vscode-progressBar-background);
            border-radius: 2px;
            margin: 12px 0;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: var(--vscode-button-background);
            transition: width 0.3s;
        }

        /* 加载动画 - 正在工作... */
        .working-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 8px 0;
            color: var(--vscode-descriptionForeground);
            font-size: 13px;
        }

        .working-indicator::after {
            content: '';
            animation: dots 1.5s infinite;
        }

        @keyframes dots {
            0%, 20% { content: ''; }
            40% { content: '.'; }
            60% { content: '..'; }
            80%, 100% { content: '...'; }
        }

        /* 代码块样式 - 带边框 */
        .markdown-content pre {
            background: #1e1e1e;
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #3c3c3c;
            overflow-x: auto;
            margin: 12px 0;
            font-family: var(--vscode-editor-font-family), 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.5;
            position: relative;
        }

        .markdown-content pre code {
            color: #d4d4d4;
            background: transparent;
            padding: 0;
        }

        /* 行内代码 - 不需要高亮 */
        .markdown-content :not(pre) > code {
            background: var(--vscode-textCodeBlock-background);
            color: var(--vscode-foreground);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }

        /* 代码块语法高亮颜色 */
        .markdown-content pre .hljs-keyword { color: #569cd6; }
        .markdown-content pre .hljs-built_in { color: #4ec9b0; }
        .markdown-content pre .hljs-type { color: #4ec9b0; }
        .markdown-content pre .hljs-literal { color: #569cd6; }
        .markdown-content pre .hljs-number { color: #b5cea8; }
        .markdown-content pre .hljs-string { color: #ce9178; }
        .markdown-content pre .hljs-comment { color: #6a9955; font-style: italic; }
        .markdown-content pre .hljs-function { color: #dcdcaa; }
        .markdown-content pre .hljs-title { color: #dcdcaa; }
        .markdown-content pre .hljs-params { color: #9cdcfe; }
        .markdown-content pre .hljs-variable { color: #9cdcfe; }
        .markdown-content pre .hljs-attr { color: #9cdcfe; }
        .markdown-content pre .hljs-tag { color: #569cd6; }
        .markdown-content pre .hljs-name { color: #4ec9b0; }
        .markdown-content pre .hljs-attribute { color: #9cdcfe; }
        .markdown-content pre .hljs-meta { color: #c586c0; }
        .markdown-content pre .hljs-preprocessor { color: #c586c0; }
        .markdown-content pre .hljs-punctuation { color: #d4d4d4; }

        /* 欢迎界面 */
        .welcome {
            text-align: center;
            padding: 40px 20px;
        }

        .welcome-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }

        .welcome-title {
            font-size: 18px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .welcome-desc {
            font-size: 13px;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 24px;
        }

        .quick-actions {
            display: flex;
            gap: 8px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .quick-action {
            padding: 8px 16px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
        }

        .quick-action:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }

        .btn-primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }

        .btn-primary:hover {
            background: var(--vscode-button-hoverBackground);
        }

        /* 错误信息 */
        .error {
            color: var(--vscode-errorForeground);
            padding: 10px 12px;
            margin: 8px 0;
            background: rgba(255, 0, 0, 0.1);
            border-radius: 6px;
        }

        .hidden { display: none; }

        /* 表格样式 */
        .markdown-content table {
            border-collapse: collapse;
            width: 100%;
            margin: 12px 0;
            font-size: 13px;
        }

        .markdown-content th, .markdown-content td {
            border: 1px solid var(--vscode-panel-border);
            padding: 8px 12px;
            text-align: left;
        }

        .markdown-content th {
            background: var(--vscode-editor-inactiveSelectionBackground);
            font-weight: 600;
        }

        .markdown-content tr:nth-child(even) {
            background: rgba(128, 128, 128, 0.05);
        }

        /* 用户消息可编辑 */
        .message-user .message-content {
            cursor: pointer;
            transition: opacity 0.2s;
        }

        .message-user .message-content:hover {
            opacity: 0.8;
        }

        .message-user .message-content.editing {
            background: var(--vscode-input-background);
            border: 1px solid var(--vscode-focusBorder);
            padding: 0;
            cursor: default;
        }

        .message-user .edit-textarea {
            width: 100%;
            min-height: 40px;
            padding: 10px 14px;
            border: none;
            background: transparent;
            color: var(--vscode-button-foreground);
            font-family: inherit;
            font-size: inherit;
            resize: none;
            outline: none;
        }

        .message-user .edit-actions {
            display: flex;
            justify-content: flex-end;
            gap: 6px;
            padding: 6px 10px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        .message-user .edit-actions button {
            padding: 4px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .message-user .edit-cancel {
            background: transparent;
            color: var(--vscode-button-foreground);
            opacity: 0.7;
        }

        .message-user .edit-send {
            background: rgba(255,255,255,0.2);
            color: var(--vscode-button-foreground);
        }

        /* 底部输入区域 */
        .input-container {
            border-top: 1px solid var(--vscode-panel-border);
            padding: 12px;
            background: var(--vscode-editor-background);
        }

        .input-wrapper {
            position: relative;
        }

        textarea#main-input {
            width: 100%;
            min-height: 50px;
            max-height: 150px;
            padding: 12px;
            padding-right: 44px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 8px;
            resize: none;
            font-family: inherit;
            font-size: 13px;
            line-height: 1.4;
        }

        textarea#main-input:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }

        .send-btn {
            position: absolute;
            right: 8px;
            bottom: 8px;
            width: 32px;
            height: 32px;
            border: none;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
        }

        .send-btn:hover {
            background: var(--vscode-button-hoverBackground);
        }

        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* 底部工具栏 */
        .toolbar {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
        }

        .selector {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            background: transparent;
            color: var(--vscode-foreground);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .selector:hover {
            background: var(--vscode-toolbar-hoverBackground);
        }

        .selector-arrow {
            opacity: 0.6;
            font-size: 10px;
        }

        .dropdown {
            position: relative;
        }

        .dropdown-menu {
            display: none;
            position: absolute;
            bottom: 100%;
            left: 0;
            min-width: 140px;
            background: var(--vscode-dropdown-background);
            border: 1px solid var(--vscode-dropdown-border);
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 100;
            margin-bottom: 4px;
            overflow: hidden;
        }

        .dropdown-menu.show {
            display: block;
        }

        .dropdown-item {
            padding: 8px 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }

        .dropdown-item:hover {
            background: var(--vscode-list-hoverBackground);
        }

        .dropdown-item.active {
            background: var(--vscode-list-activeSelectionBackground);
        }

        .dropdown-item-check {
            margin-left: auto;
            opacity: 0;
        }

        .dropdown-item.active .dropdown-item-check {
            opacity: 1;
        }

        .code-status {
            font-size: 12px;
            opacity: 0.7;
            margin-bottom: 8px;
        }

        .toolbar-spacer {
            flex: 1;
        }
    </style>
</head>
<body>
    <!-- 聊天区域 -->
    <div class="chat-container" id="chat-container">
        <!-- 欢迎界面 -->
        <div class="welcome" id="welcome">
            <div class="welcome-icon">🤖</div>
            <div class="welcome-title">TC Agent 可信计算助手</div>
            <div class="welcome-desc">AI 助手帮助您进行 OP-TEE 开发</div>
            <div class="quick-actions">
                <button class="quick-action" data-prompt="OP-TEE 如何实现 HMAC 操作？">问答示例</button>
                <button class="quick-action" data-prompt="创建一个 AES 加密的 TA">规划示例</button>
            </div>
        </div>
    </div>

    <!-- 错误信息 -->
    <div class="error hidden" id="error-msg"></div>

    <!-- 底部输入区域 -->
    <div class="input-container">
        <div class="input-wrapper">
            <textarea id="main-input" placeholder="输入您的问题..."></textarea>
            <button class="send-btn" id="send-btn">➤</button>
        </div>

        <div class="toolbar">
            <div class="dropdown" id="mode-dropdown">
                <button class="selector" id="mode-selector">
                    <span id="mode-icon">💬</span>
                    <span id="mode-text">Ask</span>
                    <span class="selector-arrow">▼</span>
                </button>
                <div class="dropdown-menu" id="mode-menu">
                    <div class="dropdown-item active" data-mode="ask">
                        <span>💬</span><span>Ask</span><span class="dropdown-item-check">✓</span>
                    </div>
                    <div class="dropdown-item" data-mode="plan">
                        <span>📋</span><span>Plan</span><span class="dropdown-item-check">✓</span>
                    </div>
                    <div class="dropdown-item" data-mode="code">
                        <span>⚡</span><span>Code</span><span class="dropdown-item-check">✓</span>
                    </div>
                </div>
            </div>

            <div class="dropdown" id="model-dropdown">
                <button class="selector" id="model-selector">
                    <span>🧠</span>
                    <span id="model-text">qwen</span>
                    <span class="selector-arrow">▼</span>
                </button>
                <div class="dropdown-menu" id="model-menu">
                    <div class="dropdown-item active" data-model="qwen">
                        <span>🧠</span><span>qwen</span><span class="dropdown-item-check">✓</span>
                    </div>
                    <div class="dropdown-item" data-model="zhipu">
                        <span>🧠</span><span>zhipu</span><span class="dropdown-item-check">✓</span>
                    </div>
                    <div class="dropdown-item" data-model="doubao">
                        <span>🧠</span><span>doubao</span><span class="dropdown-item-check">✓</span>
                    </div>
                </div>
            </div>

            <div class="toolbar-spacer"></div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentMode = 'ask';
        let currentModel = 'qwen';
        let currentWorkflowId = null;
        let currentAssistantMsg = null;
        let totalSteps = 0;
        let completedSteps = 0;
        let codeRunTimer = null;
        let codeRunStart = 0;
        let codeRunActive = false;
        let codeRunHasFinal = false;
        let currentCodeStatus = '';

        // 简单的语法高亮
        function highlightCode(code, lang) {
            // C/C++ 关键字
            const cKeywords = /\\b(auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|int|long|register|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|NULL|true|false|nullptr|class|public|private|protected|virtual|override|template|typename|namespace|using|new|delete|try|catch|throw|inline|constexpr|noexcept)\\b/g;
            // Python 关键字
            const pyKeywords = /\\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|try|while|with|yield|True|False|self)\\b/g;
            // 通用类型
            const types = /\\b(TEE_Result|TEE_Param|TEE_ObjectHandle|TEE_OperationHandle|uint32_t|uint8_t|int32_t|size_t|bool|string|int|str|list|dict|tuple|set)\\b/g;
            // 字符串
            const strings = /("([^"\\\\]|\\\\.)*"|'([^'\\\\]|\\\\.)*')/g;
            // 注释
            const comments = /(\\/\\/.*$|\\/\\*[\\s\\S]*?\\*\\/|#.*$)/gm;
            // 数字
            const numbers = /\\b(0x[0-9a-fA-F]+|\\d+\\.?\\d*)\\b/g;
            // 函数调用
            const functions = /\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*(?=\\()/g;
            // 预处理器
            const preprocessor = /^\\s*(#\\w+)/gm;

            let result = code;
            // 先处理注释和字符串（避免被其他规则影响）
            result = result.replace(comments, '<span class="hljs-comment">$1</span>');
            result = result.replace(strings, '<span class="hljs-string">$1</span>');
            result = result.replace(preprocessor, '<span class="hljs-meta">$1</span>');
            result = result.replace(numbers, '<span class="hljs-number">$1</span>');
            result = result.replace(types, '<span class="hljs-type">$1</span>');
            if (lang === 'python' || lang === 'py') {
                result = result.replace(pyKeywords, '<span class="hljs-keyword">$1</span>');
            } else {
                result = result.replace(cKeywords, '<span class="hljs-keyword">$1</span>');
            }
            result = result.replace(functions, '<span class="hljs-function">$1</span>');

            return result;
        }

        // Markdown 渲染
        function renderMarkdown(text) {
            if (!text) return '';

            // 先处理完整的代码块
            let result = text.replace(/\`\`\`(\\w*)\\n([\\s\\S]*?)\`\`\`/g, (match, lang, code) => {
                const highlighted = highlightCode(escapeHtml(code), lang);
                return '<pre><code class="language-' + lang + '">' + highlighted + '</code></pre>';
            });

            // 处理未闭合的代码块（流式输出时）
            const unclosedMatch = result.match(/\`\`\`(\\w*)\\n([\\s\\S]*)$/);
            if (unclosedMatch) {
                const lang = unclosedMatch[1];
                const code = unclosedMatch[2];
                const highlighted = highlightCode(escapeHtml(code), lang);
                result = result.replace(/\`\`\`(\\w*)\\n([\\s\\S]*)$/, '<pre><code class="language-' + lang + '">' + highlighted + '</code></pre>');
            }

            // 处理表格
            result = result.replace(/((?:^\\|.+\\|\\s*$\\n?)+)/gm, (tableMatch) => {
                const lines = tableMatch.trim().split('\\n').filter(line => line.trim());
                if (lines.length < 2) return tableMatch;

                // 检查是否有分隔行 (|---|---|)
                const separatorIndex = lines.findIndex(line => /^\\|[\\s:-]+\\|$/.test(line.replace(/[^|:-]/g, '').length > 2 ? line : ''));
                const hasSeparator = lines.some(line => /^\\s*\\|[\\s|:-]+\\|\\s*$/.test(line) && line.includes('-'));

                if (!hasSeparator) return tableMatch;

                let html = '<table>';
                let inHeader = true;

                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    // 跳过分隔行
                    if (/^\\s*\\|[\\s|:-]+\\|\\s*$/.test(line) && line.includes('-')) {
                        inHeader = false;
                        continue;
                    }

                    const cells = line.split('|').slice(1, -1).map(c => c.trim());
                    const tag = inHeader ? 'th' : 'td';
                    html += '<tr>' + cells.map(c => '<' + tag + '>' + c + '</' + tag + '>').join('') + '</tr>';
                }

                html += '</table>';
                return html;
            });

            return result
                .replace(/\`([^\`]+)\`/g, '<code>$1</code>')
                .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
                .replace(/^### (.+)$/gm, '<h3>$1</h3>')
                .replace(/^## (.+)$/gm, '<h2>$1</h2>')
                .replace(/^# (.+)$/gm, '<h1>$1</h1>')
                .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
                .replace(/^- (.+)$/gm, '<li>$1</li>')
                .replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>')
                .replace(/^\\d+\\. (.+)$/gm, '<li>$1</li>')
                .replace(/\\n\\n/g, '</p><p>')
                .replace(/\\n/g, '<br>');
        }

        // 添加用户消息
        function addUserMessage(text) {
            document.getElementById('welcome').classList.add('hidden');
            const container = document.getElementById('chat-container');
            const msg = document.createElement('div');
            msg.className = 'message message-user';
            msg.dataset.originalText = text;
            msg.innerHTML = '<div class="message-content">' + escapeHtml(text) + '</div>';

            // 点击进入编辑模式
            const content = msg.querySelector('.message-content');
            content.onclick = () => enterEditMode(msg);

            container.appendChild(msg);
            scrollToBottom();
            return msg;
        }

        // 进入编辑模式
        function enterEditMode(msg) {
            const content = msg.querySelector('.message-content');
            if (content.classList.contains('editing')) return;

            const originalText = msg.dataset.originalText;
            content.classList.add('editing');
            content.innerHTML = \`
                <textarea class="edit-textarea">\${escapeHtml(originalText)}</textarea>
                <div class="edit-actions">
                    <button class="edit-cancel">取消</button>
                    <button class="edit-send">发送</button>
                </div>
            \`;

            const textarea = content.querySelector('.edit-textarea');
            textarea.focus();
            textarea.selectionStart = textarea.value.length;

            // 自动调整高度
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
            textarea.oninput = () => {
                textarea.style.height = 'auto';
                textarea.style.height = textarea.scrollHeight + 'px';
            };

            // 取消编辑
            content.querySelector('.edit-cancel').onclick = (e) => {
                e.stopPropagation();
                exitEditMode(msg);
            };

            // 发送编辑后的消息
            content.querySelector('.edit-send').onclick = (e) => {
                e.stopPropagation();
                const newText = textarea.value.trim();
                if (newText) {
                    resendFromMessage(msg, newText);
                }
            };

            // Ctrl+Enter 发送
            textarea.onkeydown = (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    const newText = textarea.value.trim();
                    if (newText) {
                        resendFromMessage(msg, newText);
                    }
                }
                if (e.key === 'Escape') {
                    exitEditMode(msg);
                }
            };

            // 阻止点击事件冒泡
            textarea.onclick = (e) => e.stopPropagation();
        }

        // 退出编辑模式
        function exitEditMode(msg) {
            const content = msg.querySelector('.message-content');
            content.classList.remove('editing');
            content.innerHTML = escapeHtml(msg.dataset.originalText);
            content.onclick = () => enterEditMode(msg);
        }

        // 从某条消息重新发送
        function resendFromMessage(msg, newText) {
            const container = document.getElementById('chat-container');

            // 删除该消息之后的所有消息
            let sibling = msg.nextElementSibling;
            while (sibling) {
                const next = sibling.nextElementSibling;
                container.removeChild(sibling);
                sibling = next;
            }

            // 更新消息内容
            msg.dataset.originalText = newText;
            const content = msg.querySelector('.message-content');
            content.classList.remove('editing');
            content.innerHTML = escapeHtml(newText);
            content.onclick = () => enterEditMode(msg);

            // 创建新的助手消息并发送
            currentAssistantMsg = addAssistantMessage();
            currentSources = null;

            switch(currentMode) {
                case 'ask':
                    vscode.postMessage({ command: 'ask', query: newText });
                    break;
                case 'plan':
                    vscode.postMessage({ command: 'plan', task: newText });
                    break;
                case 'code':
                    vscode.postMessage({ command: 'directExecute', task: newText });
                    break;
            }
        }

        // 添加助手消息（返回消息元素以便更新）
        function addAssistantMessage(statusText = '正在思考') {
            const container = document.getElementById('chat-container');
            const msg = document.createElement('div');
            msg.className = 'message message-assistant';
            msg.innerHTML = '<div class="message-content"><div class="working-indicator">' + statusText + '</div></div>';
            container.appendChild(msg);
            scrollToBottom();
            return msg;
        }

        // 更新加载状态文字
        function updateWorkingStatus(msg, statusText) {
            const indicator = msg.querySelector('.working-indicator');
            if (indicator) {
                indicator.textContent = statusText;
            }
        }

        function formatElapsed(ms) {
            const totalSeconds = Math.floor(ms / 1000);
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = totalSeconds % 60;
            if (minutes > 0) {
                return minutes + 'm ' + String(seconds).padStart(2, '0') + 's';
            }
            return totalSeconds + 's';
        }

        function ensureCodeStatusElement(msg) {
            let statusEl = msg.querySelector('.code-status');
            if (statusEl) return statusEl;

            const content = msg.querySelector('.message-content');
            if (!content) return null;

            statusEl = document.createElement('div');
            statusEl.className = 'code-status';
            statusEl.textContent = currentCodeStatus || '执行中';

            const agentEvents = content.querySelector('.agent-events');
            if (agentEvents) {
                content.insertBefore(statusEl, agentEvents);
            } else {
                content.prepend(statusEl);
            }
            return statusEl;
        }

        function updateCodeStatus(statusText) {
            currentCodeStatus = statusText;
            if (!currentAssistantMsg) return;

            const indicator = currentAssistantMsg.querySelector('.working-indicator');
            if (indicator) {
                indicator.textContent = statusText;
                return;
            }

            const statusEl = ensureCodeStatusElement(currentAssistantMsg);
            if (statusEl) {
                statusEl.textContent = statusText;
            }
        }

        function startCodeRun() {
            codeRunActive = true;
            codeRunHasFinal = false;
            codeRunStart = Date.now();
            updateCodeStatus('执行中 · 已运行 0s');
            if (codeRunTimer) {
                clearInterval(codeRunTimer);
            }
            codeRunTimer = setInterval(() => {
                if (!codeRunActive) return;
                const elapsed = formatElapsed(Date.now() - codeRunStart);
                updateCodeStatus('执行中 · 已运行 ' + elapsed);
            }, 1000);
        }

        function finishCodeRun(statusText) {
            codeRunActive = false;
            if (codeRunTimer) {
                clearInterval(codeRunTimer);
                codeRunTimer = null;
            }
            if (statusText) {
                updateCodeStatus(statusText);
            }
        }

        // 更新助手消息内容
        function updateAssistantMessage(msg, content, sources = null) {
            let html = '';

            // 来源折叠区域（放在回答前面）
            if (sources && sources.length > 0) {
                html += '<details class="sources-collapse"><summary>✓ 检索到 ' + sources.length + ' 个相关文档</summary>';
                html += '<div class="sources-content">';
                sources.forEach(s => {
                    const filename = s.source.split('/').pop();
                    const score = Math.round(s.score * 100);
                    html += '<div class="source-item">' + filename + ' <span style="opacity:0.6">(' + score + '%)</span></div>';
                });
                html += '</div></details>';
            }

            // 回答内容
            html += '<div class="markdown-content">' + renderMarkdown(content) + '</div>';

            msg.querySelector('.message-content').innerHTML = html;
            scrollToBottom();
        }

        // Plan 步骤显示
        function showPlanSteps(msg, steps, workflowId) {
            currentWorkflowId = workflowId;
            totalSteps = steps.length;

            let html = '<div class="plan-steps">';
            steps.forEach((s, i) => {
                html += '<div class="step-item" id="step-' + i + '">' + s.id + '. ' + s.description + '</div>';
            });
            html += '</div>';

            html += '<div class="plan-actions">';
            html += '<textarea id="refine-input" placeholder="输入修改指令..."></textarea>';
            html += '<button class="quick-action" id="refine-btn">修改计划</button>';
            html += '<button class="quick-action btn-primary" id="confirm-btn">✓ 确认执行</button>';
            html += '</div>';

            msg.querySelector('.message-content').innerHTML = html;

            // 绑定事件
            document.getElementById('refine-btn').onclick = () => {
                const instruction = document.getElementById('refine-input').value.trim();
                if (instruction && currentWorkflowId) {
                    vscode.postMessage({ command: 'refinePlan', workflowId: currentWorkflowId, instruction });
                }
            };
            document.getElementById('confirm-btn').onclick = () => {
                if (currentWorkflowId) {
                    vscode.postMessage({ command: 'confirmPlan', workflowId: currentWorkflowId });
                }
            };

            scrollToBottom();
        }

        // Agent 事件输出
        function addAgentEvent(msg, type, content) {
            let eventContainer = msg.querySelector('.agent-events');
            if (!eventContainer) {
                msg.querySelector('.message-content').innerHTML = '<div class="agent-events"></div>';
                eventContainer = msg.querySelector('.agent-events');
            }

            const event = document.createElement('div');
            event.className = 'agent-event event-' + type;

            const label = document.createElement('div');
            label.className = 'event-label';
            switch(type) {
                case 'thought': label.textContent = '💭 思考'; break;
                case 'action': label.textContent = '🔧 行动'; break;
                case 'observation': label.textContent = '👁 观察'; break;
            }
            event.appendChild(label);

            const contentEl = document.createElement('div');
            contentEl.textContent = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
            event.appendChild(contentEl);

            eventContainer.appendChild(event);
            if (currentCodeStatus) {
                updateCodeStatus(currentCodeStatus);
            }
            scrollToBottom();
        }

        // 显示最终结果
        function showFinalResult(msg, answer) {
            let eventContainer = msg.querySelector('.agent-events');
            if (eventContainer) {
                eventContainer.innerHTML += '<div class="markdown-content" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--vscode-panel-border);">' + renderMarkdown(answer) + '</div>';
            } else {
                msg.querySelector('.message-content').innerHTML = '<div class="markdown-content">' + renderMarkdown(answer) + '</div>';
            }
            scrollToBottom();
        }

        function scrollToBottom() {
            const container = document.getElementById('chat-container');
            container.scrollTop = container.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 下拉菜单
        function setupDropdown(dropdownId, menuId, onSelect) {
            const dropdown = document.getElementById(dropdownId);
            const menu = document.getElementById(menuId);
            dropdown.querySelector('.selector').onclick = (e) => {
                e.stopPropagation();
                document.querySelectorAll('.dropdown-menu').forEach(m => m !== menu && m.classList.remove('show'));
                menu.classList.toggle('show');
            };
            menu.querySelectorAll('.dropdown-item').forEach(item => {
                item.onclick = () => {
                    menu.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    menu.classList.remove('show');
                    onSelect(item);
                };
            });
        }

        document.addEventListener('click', () => {
            document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
        });

        setupDropdown('mode-dropdown', 'mode-menu', (item) => {
            currentMode = item.dataset.mode;
            document.getElementById('mode-icon').textContent = item.querySelector('span').textContent;
            document.getElementById('mode-text').textContent = item.querySelectorAll('span')[1].textContent;
            const placeholders = {
                ask: '输入您的问题...',
                plan: '描述您要完成的任务...',
                code: '输入要执行的任务...'
            };
            document.getElementById('main-input').placeholder = placeholders[currentMode];
            vscode.postMessage({ command: 'switchMode', mode: currentMode });
        });

        setupDropdown('model-dropdown', 'model-menu', (item) => {
            currentModel = item.dataset.model;
            document.getElementById('model-text').textContent = currentModel;
            vscode.postMessage({ command: 'switchModel', model: currentModel });
        });

        // 发送消息
        document.getElementById('send-btn').onclick = sendMessage;
        document.getElementById('main-input').onkeydown = (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                sendMessage();
            }
        };

        function sendMessage() {
            const input = document.getElementById('main-input');
            const text = input.value.trim();
            if (!text) return;

            addUserMessage(text);
            currentAssistantMsg = addAssistantMessage();

            switch(currentMode) {
                case 'ask':
                    vscode.postMessage({ command: 'ask', query: text });
                    break;
                case 'plan':
                    vscode.postMessage({ command: 'plan', task: text });
                    break;
                case 'code':
                    vscode.postMessage({ command: 'directExecute', task: text });
                    break;
            }

            input.value = '';
        }

        // 快速操作
        document.querySelectorAll('.quick-action[data-prompt]').forEach(btn => {
            btn.onclick = () => {
                document.getElementById('main-input').value = btn.dataset.prompt;
                document.getElementById('main-input').focus();
            };
        });

        // 存储来源数据
        let currentSources = null;

        // 消息处理
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'askResponse':
                    if (currentAssistantMsg) {
                        updateAssistantMessage(currentAssistantMsg, message.content, currentSources);
                    }
                    break;

                case 'sources':
                    currentSources = message.sources;
                    break;

                case 'status':
                    if (currentAssistantMsg) {
                        updateWorkingStatus(currentAssistantMsg, message.status);
                    }
                    break;

                case 'planResponse':
                    if (currentAssistantMsg) {
                        showPlanSteps(currentAssistantMsg, message.steps, message.workflowId);
                    }
                    break;

                case 'planConfirmed':
                    currentAssistantMsg = addAssistantMessage();
                    break;

                case 'setMode':
                    document.querySelector('[data-mode="' + message.mode + '"]').click();
                    break;

                case 'codeStart':
                    startCodeRun();
                    break;

                case 'thought':
                    if (currentAssistantMsg) {
                        addAgentEvent(currentAssistantMsg, 'thought', message.content);
                    }
                    break;

                case 'action':
                    if (currentAssistantMsg) {
                        addAgentEvent(currentAssistantMsg, 'action', message.tool + ': ' + JSON.stringify(message.input));
                    }
                    break;

                case 'observation':
                    if (currentAssistantMsg) {
                        addAgentEvent(currentAssistantMsg, 'observation', message.content);
                    }
                    break;

                case 'codeResult':
                    if (currentAssistantMsg) {
                        showFinalResult(currentAssistantMsg, message.answer);
                    }
                    codeRunHasFinal = true;
                    finishCodeRun('✅ 执行完成');
                    currentSources = null;
                    break;

                case 'codeComplete':
                    if (!codeRunHasFinal) {
                        finishCodeRun('✅ 执行结束（无最终输出）');
                    } else {
                        finishCodeRun('✅ 执行完成');
                    }
                    currentSources = null;
                    break;

                case 'error':
                    if (currentAssistantMsg) {
                        currentAssistantMsg.querySelector('.message-content').innerHTML = '<div class="error">❌ ' + message.message + '</div>';
                    }
                    codeRunHasFinal = true;
                    finishCodeRun();
                    currentSources = null;
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}
