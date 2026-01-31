import { ViewState } from './state';

export function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export function scrollToBottom(): void {
    const container = document.getElementById('chat-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

export function highlightCode(code: string, lang: string): string {
    const cKeywords = /\b(auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|int|long|register|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|NULL|true|false|nullptr|class|public|private|protected|virtual|override|template|typename|namespace|using|new|delete|try|catch|throw|inline|constexpr|noexcept)\b/g;
    const pyKeywords = /\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|try|while|with|yield|True|False|self)\b/g;
    const types = /\b(TEE_Result|TEE_Param|TEE_ObjectHandle|TEE_OperationHandle|uint32_t|uint8_t|int32_t|size_t|bool|string|int|str|list|dict|tuple|set)\b/g;
    const strings = /("([^"\\]|\\.)*"|'([^'\\]|\\.)*')/g;
    const comments = /(\/\/.*$|\/\*[\s\S]*?\*\/|#.*$)/gm;
    const numbers = /\b(0x[0-9a-fA-F]+|\d+\.?\d*)\b/g;
    const functions = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/g;
    const preprocessor = /^\s*(#\w+)/gm;

    let result = code;
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

export function renderMarkdown(text: string): string {
    if (!text) return '';

    let result = text.replace(/\`\`\`(\w*)\n([\s\S]*?)\`\`\`/g, (match, lang, code) => {
        const highlighted = highlightCode(escapeHtml(code), lang);
        return '<pre><code class="language-' + lang + '">' + highlighted + '</code></pre>';
    });

    const unclosedMatch = result.match(/\`\`\`(\w*)\n([\s\S]*)$/);
    if (unclosedMatch) {
        const lang = unclosedMatch[1];
        const code = unclosedMatch[2];
        const highlighted = highlightCode(escapeHtml(code), lang);
        result = result.replace(/\`\`\`(\w*)\n([\s\S]*)$/, '<pre><code class="language-' + lang + '">' + highlighted + '</code></pre>');
    }

    result = result.replace(/((?:^\|.+\|\s*$\n?)+)/gm, (tableMatch) => {
        const lines = tableMatch.trim().split('\n').filter(line => line.trim());
        if (lines.length < 2) return tableMatch;
        const hasSeparator = lines.some(line => /^\s*\|[\s|:-]+\|\s*$/.test(line) && line.includes('-'));
        if (!hasSeparator) return tableMatch;

        let html = '<table>';
        let inHeader = true;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (/^\s*\|[\s|:-]+\|\s*$/.test(line) && line.includes('-')) {
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
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}

export function addAssistantMessage(state: ViewState, statusText = '正在思考'): HTMLElement {
    const container = document.getElementById('chat-container');
    const msg = document.createElement('div');
    msg.className = 'message message-assistant';
    msg.innerHTML = '<div class="message-content"><div class="working-indicator">' + statusText + '</div></div>';
    container?.appendChild(msg);
    scrollToBottom();
    state.currentAssistantMsg = msg;
    return msg;
}

export function updateWorkingStatus(msg: HTMLElement, statusText: string): void {
    const indicator = msg.querySelector('.working-indicator');
    if (indicator) {
        indicator.textContent = statusText;
    }
}

export function updateAssistantMessage(msg: HTMLElement, content: string, sources: any[] | null = null): void {
    let html = '';
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

    html += '<div class="markdown-content">' + renderMarkdown(content) + '</div>';
    msg.querySelector('.message-content')!.innerHTML = html;
    scrollToBottom();
}

export function addAgentEvent(msg: HTMLElement, type: string, content: any, containerOverride: HTMLElement | null = null): void {
    let eventContainer = containerOverride || msg.querySelector('.code-details .agent-events') || msg.querySelector('.agent-events');
    if (!eventContainer) {
        msg.querySelector('.message-content')!.innerHTML = '<div class="agent-events"></div>';
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

    eventContainer!.appendChild(event);
    scrollToBottom();
}

export function addMilestone(text: string, status: string, containerOverride: HTMLElement | null = null): HTMLElement {
    const container = containerOverride || document.querySelector('.code-milestones');
    const item = document.createElement('div');
    item.className = 'milestone ' + status;
    item.textContent = text;
    container?.appendChild(item);
    return item;
}

export function updateMilestone(item: HTMLElement | null, status: string): void {
    if (!item) return;
    item.className = 'milestone ' + status;
}

export function initCodeRunView(state: ViewState, msg: HTMLElement): void {
    msg.querySelector('.message-content')!.innerHTML =
        '<div class="code-run">' +
        '<div class="code-status">执行中</div>' +
        '<div class="code-steps"></div>' +
        '<details class="code-details" open>' +
        '<summary>执行详情</summary>' +
        '<div class="agent-events"></div>' +
        '</details>' +
        '</div>';

    state.stepEventContainers = {};
    state.stepMilestoneContainers = {};
    state.stepStatusLabels = {};
}

export function updateCodeStatus(state: ViewState, statusText: string): void {
    state.currentCodeStatus = statusText;
    if (!state.currentAssistantMsg) return;
    const statusEl = state.currentAssistantMsg.querySelector('.code-status');
    if (statusEl) {
        statusEl.textContent = statusText;
    }
    const indicator = state.currentAssistantMsg.querySelector('.working-indicator');
    if (indicator) {
        indicator.textContent = statusText;
    }
}

export function setStopButtonState(enabled: boolean, label = '停止执行'): void {
    const stopBtn = document.getElementById('stop-btn') as HTMLButtonElement | null;
    if (!stopBtn) return;
    stopBtn.disabled = enabled;
    stopBtn.textContent = label;
}

export function ensureStepBlock(state: ViewState, stepIndex: number, step: any): void {
    if (!state.currentAssistantMsg) return;
    const codeRun = state.currentAssistantMsg.querySelector('.code-run');
    if (!codeRun) return;

    const stepsContainer = codeRun.querySelector('.code-steps');
    if (!stepsContainer) return;

    const existing = stepsContainer.querySelector(`#code-step-${stepIndex}`) as HTMLElement | null;
    if (existing) return;

    const stepEl = document.createElement('div');
    stepEl.className = 'code-step';
    stepEl.id = `code-step-${stepIndex}`;
    stepEl.innerHTML =
        '<div class="code-step-header">' +
        '<div class="code-step-title">步骤 ' + (step?.id || (stepIndex + 1)) + ': ' + (step?.description || '') + '</div>' +
        '<div class="code-step-status">进行中</div>' +
        '</div>' +
        '<div class="code-step-milestones"></div>' +
        '<div class="agent-events"></div>';

    stepsContainer.appendChild(stepEl);
    state.stepEventContainers[stepIndex] = stepEl.querySelector('.agent-events') as HTMLElement;
    state.stepMilestoneContainers[stepIndex] = stepEl.querySelector('.code-step-milestones') as HTMLElement;
    state.stepStatusLabels[stepIndex] = stepEl.querySelector('.code-step-status') as HTMLElement;
}

export function setStepStatus(state: ViewState, stepIndex: number, statusText: string): void {
    const status = state.stepStatusLabels[stepIndex];
    if (status) {
        status.textContent = statusText;
    }
}

export function setAllStepStatuses(state: ViewState, statusText: string, onlyInProgress = false): void {
    Object.keys(state.stepStatusLabels).forEach(key => {
        const status = state.stepStatusLabels[Number(key)];
        if (!status) return;
        if (onlyInProgress && status.textContent !== '进行中') return;
        status.textContent = statusText;
    });
}

export function showFinalResult(msg: HTMLElement, answer: string): void {
    const codeRun = msg.querySelector('.code-run');
    if (codeRun) {
        let result = codeRun.querySelector('.code-result');
        if (!result) {
            result = document.createElement('div');
            result.className = 'code-result';
            const details = codeRun.querySelector('.code-details');
            if (details) {
                codeRun.insertBefore(result, details);
            }
        }
        result.innerHTML = '<div class="markdown-content">' + renderMarkdown(answer) + '</div>';
    } else {
        const eventContainer = msg.querySelector('.agent-events');
        if (eventContainer) {
            eventContainer.innerHTML += '<div class="markdown-content" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--vscode-panel-border);">' + renderMarkdown(answer) + '</div>';
        } else {
            msg.querySelector('.message-content')!.innerHTML = '<div class="markdown-content">' + renderMarkdown(answer) + '</div>';
        }
    }
    scrollToBottom();
}

export function showPlanSteps(state: ViewState, msg: HTMLElement, steps: any[], workflowId: string, handlers: { onRefine: (instruction: string) => void; onConfirm: () => void; }): void {
    state.currentWorkflowId = workflowId;
    state.totalSteps = steps.length;

    let html = '<div class="plan-card">';
    html += '<div class="plan-header">';
    html += '<div>';
    html += '<div class="plan-title">计划预览</div>';
    html += '<div class="plan-meta">共 ' + steps.length + ' 步 · 确认后自动执行</div>';
    html += '</div>';
    html += '<div class="plan-actions-inline">';
    html += '<button class="quick-action" id="refine-toggle">修改计划</button>';
    html += '<button class="quick-action btn-primary" id="confirm-btn">✓ 确认执行</button>';
    html += '</div>';
    html += '</div>';

    html += '<div class="plan-steps">';
    steps.forEach((s, i) => {
        const stepLabel = s.id || (i + 1);
        html += '<div class="plan-step" id="step-' + i + '">';
        html += '<div class="plan-step-index">' + escapeHtml(String(stepLabel)) + '</div>';
        html += '<div class="plan-step-text">' + escapeHtml(s.description || '') + '</div>';
        html += '</div>';
    });
    html += '</div>';

    html += '<div class="plan-refine hidden" id="refine-panel">';
    html += '<div class="plan-refine-title">修改计划</div>';
    html += '<textarea id="refine-input" placeholder="例如：合并步骤 2 和 3，删除步骤 4"></textarea>';
    html += '<div class="plan-refine-actions">';
    html += '<button class="quick-action" id="refine-btn">应用修改</button>';
    html += '<button class="quick-action" id="refine-cancel">取消</button>';
    html += '</div>';
    html += '</div>';
    html += '</div>';

    msg.querySelector('.message-content')!.innerHTML = html;

    const refinePanel = document.getElementById('refine-panel') as HTMLElement;
    const refineToggle = document.getElementById('refine-toggle') as HTMLElement;
    const refineInput = document.getElementById('refine-input') as HTMLTextAreaElement;
    const refineCancel = document.getElementById('refine-cancel') as HTMLElement;

    refineToggle.onclick = () => {
        refinePanel.classList.toggle('hidden');
        refineToggle.textContent = refinePanel.classList.contains('hidden') ? '修改计划' : '收起修改';
        if (!refinePanel.classList.contains('hidden')) {
            refineInput.focus();
        }
    };

    refineCancel.onclick = () => {
        refinePanel.classList.add('hidden');
        refineToggle.textContent = '修改计划';
        refineInput.value = '';
    };

    const refineBtn = document.getElementById('refine-btn') as HTMLElement;
    refineBtn.onclick = () => {
        const instruction = refineInput.value.trim();
        if (instruction) {
            handlers.onRefine(instruction);
        }
    };

    const confirmBtn = document.getElementById('confirm-btn') as HTMLElement;
    confirmBtn.onclick = () => handlers.onConfirm();

    refineInput.onkeydown = (e: KeyboardEvent) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            const instruction = refineInput.value.trim();
            if (instruction) {
                handlers.onRefine(instruction);
            }
        }
    };

    scrollToBottom();
}

export function getActiveMilestoneContainer(state: ViewState): HTMLElement | null {
    if (state.activeStepIndex !== null && state.stepMilestoneContainers[state.activeStepIndex]) {
        return state.stepMilestoneContainers[state.activeStepIndex];
    }
    if (!state.currentAssistantMsg) return null;
    return state.currentAssistantMsg.querySelector('.code-milestones') as HTMLElement | null;
}

export function getActiveEventContainer(state: ViewState): HTMLElement | null {
    if (state.activeStepIndex !== null && state.stepEventContainers[state.activeStepIndex]) {
        return state.stepEventContainers[state.activeStepIndex];
    }
    if (!state.currentAssistantMsg) return null;
    return state.currentAssistantMsg.querySelector('.code-details .agent-events') as HTMLElement | null || state.currentAssistantMsg.querySelector('.agent-events') as HTMLElement | null;
}

export function maybeAddFileMilestone(state: ViewState, content: string, containerOverride: HTMLElement | null = null): void {
    if (!content || typeof content !== 'string') return;
    if (!content.includes('path')) return;
    const match = content.match(/path['":\s]+([^'"\s,}]+)/);
    if (match && match[1]) {
        addMilestone('生成文件 ' + match[1], 'success', containerOverride);
    }
}

export function formatElapsed(ms: number): string {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (minutes === 0) return `${seconds}s`;
    return `${minutes}m${seconds}s`;
}
