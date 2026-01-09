import * as vscode from 'vscode';
import { IAgentClient, Mode, Workflow } from '../../agent/types';
import { AskMode, PlanMode, CodeMode } from '../../modes';
import { ConversationState, WorkflowState } from '../../state';
import { logger } from '../../utils';

export class ChatViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'tcAgent.chatView';
  private _view?: vscode.WebviewView;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly agentClient: IAgentClient,
    private readonly conversationState: ConversationState,
    private readonly workflowState: WorkflowState
  ) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    // Handle messages from webview
    webviewView.webview.onDidReceiveMessage(async (data) => {
      await this._handleMessage(data);
    });

    // Load conversation history
    this._sendHistoryToWebview();
  }

  private async _handleMessage(data: any) {
    try {
      switch (data.type) {
        case 'sendMessage':
          await this._handleSendMessage(data.mode, data.message);
          break;
        case 'confirmWorkflow':
          await this._handleConfirmWorkflow();
          break;
        case 'clearHistory':
          this._handleClearHistory();
          break;
        default:
          logger.warn(`Unknown message type: ${data.type}`);
      }
    } catch (error) {
      logger.error('Error handling message', error);
      this._sendToWebview({
        type: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private async _handleSendMessage(mode: Mode, message: string) {
    // Send user message to webview
    this._sendToWebview({
      type: 'userMessage',
      message,
      timestamp: Date.now(),
    });

    // Show loading state
    this._sendToWebview({
      type: 'loading',
      isLoading: true,
    });

    try {
      if (mode === 'ask') {
        const askMode = new AskMode(this.agentClient, this.conversationState);
        const reply = await askMode.handleMessage(message);
        this._sendToWebview({
          type: 'assistantMessage',
          message: reply,
          timestamp: Date.now(),
        });
      } else if (mode === 'plan') {
        const planMode = new PlanMode(
          this.agentClient,
          this.conversationState,
          this.workflowState
        );
        const result = await planMode.handleMessage(message);
        this._sendToWebview({
          type: 'assistantMessage',
          message: result.reply,
          timestamp: Date.now(),
        });
        if (result.workflow) {
          this._sendToWebview({
            type: 'workflow',
            workflow: result.workflow,
          });
        }
      } else if (mode === 'code') {
        const codeMode = new CodeMode(this.agentClient, this.workflowState);
        const workflow = codeMode.getCurrentWorkflow();
        if (workflow && workflow.status === 'confirmed') {
          await codeMode.executeWorkflow(workflow);
          this._sendToWebview({
            type: 'assistantMessage',
            message: 'Workflow 执行完成！',
            timestamp: Date.now(),
          });
        } else {
          this._sendToWebview({
            type: 'assistantMessage',
            message: '请先在 PLAN 模式下创建并确认 Workflow',
            timestamp: Date.now(),
          });
        }
      }
    } finally {
      this._sendToWebview({
        type: 'loading',
        isLoading: false,
      });
    }
  }

  private async _handleConfirmWorkflow() {
    const planMode = new PlanMode(
      this.agentClient,
      this.conversationState,
      this.workflowState
    );
    const workflow = planMode.confirmWorkflow();
    if (workflow) {
      this._sendToWebview({
        type: 'workflowConfirmed',
        workflow,
      });
      this._sendToWebview({
        type: 'assistantMessage',
        message: 'Workflow 已确认，可以切换到 CODE 模式执行',
        timestamp: Date.now(),
      });
    }
  }

  private _handleClearHistory() {
    this.conversationState.clear();
    this.workflowState.clearCurrent();
    this._sendToWebview({
      type: 'historyCleared',
    });
  }

  private _sendHistoryToWebview() {
    const messages = this.conversationState.getMessages();
    const workflow = this.workflowState.getCurrentWorkflow();
    this._sendToWebview({
      type: 'history',
      messages,
      workflow,
    });
  }

  private _sendToWebview(message: any) {
    if (this._view) {
      this._view.webview.postMessage(message);
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TC Agent Chat</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      background-color: var(--vscode-editor-background);
      padding: 10px;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .header {
      margin-bottom: 10px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    .mode-selector {
      display: flex;
      gap: 5px;
      margin-bottom: 10px;
    }
    .mode-btn {
      padding: 5px 15px;
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: 1px solid var(--vscode-button-border);
      border-radius: 3px;
      cursor: pointer;
      font-size: 12px;
    }
    .mode-btn.active {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
    }
    .messages {
      flex: 1;
      overflow-y: auto;
      margin-bottom: 10px;
      padding: 10px;
      background: var(--vscode-editor-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: 3px;
    }
    .message {
      margin-bottom: 15px;
      padding: 10px;
      border-radius: 5px;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .message.user {
      background: var(--vscode-inputValidation-infoBorder);
      color: var(--vscode-input-foreground);
    }
    .message.assistant {
      background: var(--vscode-editor-inactiveSelectionBackground);
    }
    .workflow-preview {
      margin: 10px 0;
      padding: 10px;
      background: var(--vscode-textBlockQuote-background);
      border-left: 3px solid var(--vscode-textBlockQuote-border);
      border-radius: 3px;
    }
    .workflow-step {
      padding: 5px;
      margin: 5px 0;
      font-size: 12px;
    }
    .input-area {
      display: flex;
      gap: 5px;
    }
    textarea {
      flex: 1;
      padding: 8px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 3px;
      resize: none;
      font-family: inherit;
      font-size: inherit;
    }
    button {
      padding: 8px 16px;
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 3px;
      cursor: pointer;
      font-size: 13px;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .loading {
      text-align: center;
      padding: 10px;
      color: var(--vscode-descriptionForeground);
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="mode-selector">
      <button class="mode-btn active" data-mode="ask">ASK</button>
      <button class="mode-btn" data-mode="plan">PLAN</button>
      <button class="mode-btn" data-mode="code">CODE</button>
    </div>
    <button onclick="clearHistory()" style="font-size: 11px; padding: 3px 8px;">清除历史</button>
  </div>

  <div class="messages" id="messages"></div>

  <div class="input-area">
    <textarea id="input" placeholder="输入消息..." rows="3"></textarea>
    <button onclick="sendMessage()">发送</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    let currentMode = 'ask';
    let isLoading = false;
    let currentWorkflow = null;

    // Mode selection
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
      });
    });

    // Send message
    function sendMessage() {
      const input = document.getElementById('input');
      const message = input.value.trim();
      if (!message || isLoading) return;

      vscode.postMessage({
        type: 'sendMessage',
        mode: currentMode,
        message: message
      });

      input.value = '';
    }

    // Clear history
    function clearHistory() {
      vscode.postMessage({ type: 'clearHistory' });
    }

    // Confirm workflow
    function confirmWorkflow() {
      vscode.postMessage({ type: 'confirmWorkflow' });
    }

    // Handle Enter key
    document.getElementById('input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Handle messages from extension
    window.addEventListener('message', event => {
      const data = event.data;
      const messagesDiv = document.getElementById('messages');

      switch (data.type) {
        case 'userMessage':
          addMessage('user', data.message);
          break;
        case 'assistantMessage':
          addMessage('assistant', data.message);
          break;
        case 'workflow':
          currentWorkflow = data.workflow;
          showWorkflow(data.workflow);
          break;
        case 'workflowConfirmed':
          currentWorkflow = data.workflow;
          addMessage('assistant', 'Workflow 已确认！');
          break;
        case 'loading':
          isLoading = data.isLoading;
          if (isLoading) {
            const loading = document.createElement('div');
            loading.className = 'loading';
            loading.id = 'loading-indicator';
            loading.textContent = '思考中...';
            messagesDiv.appendChild(loading);
          } else {
            const loading = document.getElementById('loading-indicator');
            if (loading) loading.remove();
          }
          messagesDiv.scrollTop = messagesDiv.scrollHeight;
          break;
        case 'history':
          loadHistory(data.messages, data.workflow);
          break;
        case 'historyCleared':
          messagesDiv.innerHTML = '';
          currentWorkflow = null;
          break;
        case 'error':
          addMessage('assistant', 'Error: ' + data.message);
          break;
      }
    });

    function addMessage(role, content) {
      const messagesDiv = document.getElementById('messages');
      const messageDiv = document.createElement('div');
      messageDiv.className = 'message ' + role;
      messageDiv.textContent = content;
      messagesDiv.appendChild(messageDiv);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function showWorkflow(workflow) {
      const messagesDiv = document.getElementById('messages');
      const workflowDiv = document.createElement('div');
      workflowDiv.className = 'workflow-preview';

      let html = '<strong>Workflow: ' + workflow.name + '</strong><br>';
      html += '<small>Status: ' + workflow.status + '</small><br>';
      workflow.steps.forEach((step, i) => {
        html += '<div class="workflow-step">';
        html += (i + 1) + '. ' + step.tool + ' - ' + step.status;
        html += '</div>';
      });

      if (workflow.status === 'draft') {
        html += '<button onclick="confirmWorkflow()" style="margin-top: 10px; font-size: 12px; padding: 5px 10px;">确认 Workflow</button>';
      }

      workflowDiv.innerHTML = html;
      messagesDiv.appendChild(workflowDiv);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function loadHistory(messages, workflow) {
      const messagesDiv = document.getElementById('messages');
      messagesDiv.innerHTML = '';
      messages.forEach(msg => {
        addMessage(msg.role, msg.content);
      });
      if (workflow) {
        currentWorkflow = workflow;
        showWorkflow(workflow);
      }
    }
  </script>
</body>
</html>`;
  }
}
