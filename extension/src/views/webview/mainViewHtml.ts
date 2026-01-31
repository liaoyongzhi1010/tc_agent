import * as vscode from 'vscode';

export function getMainViewHtml(webview: vscode.Webview, extensionUri: vscode.Uri): string {
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'mainView.js'));
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
        .plan-card {
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 12px;
            background: var(--vscode-editorWidget-background, var(--vscode-editor-background));
        }

        .plan-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }

        .plan-title {
            font-size: 13px;
            font-weight: 600;
        }

        .plan-meta {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 2px;
        }

        .plan-actions-inline {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .plan-steps {
            margin: 10px 0;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .plan-step {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            padding: 8px 10px;
            border-radius: 6px;
            border: 1px solid var(--vscode-panel-border);
            background: var(--vscode-editor-inactiveSelectionBackground);
        }

        .plan-step-index {
            width: 22px;
            height: 22px;
            border-radius: 999px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .plan-step-text {
            font-size: 13px;
            line-height: 1.4;
        }

        .plan-refine {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px dashed var(--vscode-panel-border);
        }

        .plan-refine-title {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 6px;
        }

        .plan-refine textarea {
            width: 100%;
            min-height: 48px;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 6px;
            resize: none;
            font-family: inherit;
            margin-bottom: 8px;
        }

        .plan-refine-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
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

        .code-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
        }

        .code-status {
            font-size: 12px;
            opacity: 0.7;
        }

        .code-stop {
            padding: 4px 10px;
            border: 1px solid var(--vscode-button-border, transparent);
            background: var(--vscode-button-secondaryBackground, var(--vscode-button-background));
            color: var(--vscode-button-secondaryForeground, var(--vscode-button-foreground));
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .code-stop[disabled] {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .code-milestones {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 10px;
        }

        .code-steps {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
        }

        .code-step {
            border: 1px solid var(--vscode-panel-border);
            border-radius: 6px;
            padding: 8px;
        }

        .code-step-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            margin-bottom: 6px;
        }

        .code-step-status {
            opacity: 0.7;
        }

        .code-step-milestones {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 8px;
        }

        .milestone {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
        }

        .milestone.pending::before {
            content: '⏳';
        }

        .milestone.success::before {
            content: '✅';
        }

        .milestone.fail::before {
            content: '❌';
        }

        .code-details summary {
            cursor: pointer;
            font-size: 12px;
            opacity: 0.7;
            margin-bottom: 6px;
        }

        .code-run.has-steps .code-details {
            display: none;
        }

        .code-run.has-steps .code-milestones {
            display: none;
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
                <button class="quick-action" data-prompt="生成一个 HELLO TA/CA，并运行 QEMU 做验证">Agent 示例</button>
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
                    <div class="dropdown-item" data-mode="agent">
                        <span>🤖</span><span>Agent</span><span class="dropdown-item-check">✓</span>
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

    <script src="${scriptUri}"></script>
</body>
</html>`;
}
