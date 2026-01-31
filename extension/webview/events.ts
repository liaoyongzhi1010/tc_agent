import { ViewState } from './state';
import {
    escapeHtml,
    scrollToBottom,
    addAssistantMessage,
    updateAssistantMessage,
    updateWorkingStatus,
    showPlanSteps,
    addAgentEvent,
    addMilestone,
    updateMilestone,
    getActiveEventContainer,
    getActiveMilestoneContainer,
    maybeAddFileMilestone,
    ensureStepBlock,
    setStepStatus,
    showFinalResult,
    updateCodeStatus,
    setStopButtonState,
    setAllStepStatuses,
    initCodeRunView,
    formatElapsed
} from './ui';

export function bindDomEvents(state: ViewState, vscode: any): void {
    document.addEventListener('click', () => {
        document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
    });

    setupDropdown('mode-dropdown', 'mode-menu', (item) => {
        state.currentMode = item.dataset.mode as 'ask' | 'agent';
        document.getElementById('mode-icon')!.textContent = item.querySelector('span')!.textContent || '';
        document.getElementById('mode-text')!.textContent = item.querySelectorAll('span')[1].textContent || '';
        const placeholders: Record<string, string> = {
            ask: '输入您的问题...',
            agent: '描述您要完成的任务...'
        };
        (document.getElementById('main-input') as HTMLTextAreaElement).placeholder = placeholders[state.currentMode];
        vscode.postMessage({ command: 'switchMode', mode: state.currentMode });
    });

    setupDropdown('model-dropdown', 'model-menu', (item) => {
        state.currentModel = item.dataset.model;
        document.getElementById('model-text')!.textContent = state.currentModel;
        vscode.postMessage({ command: 'switchModel', model: state.currentModel });
    });

    document.getElementById('send-btn')!.onclick = () => sendMessage(state, vscode);
    document.getElementById('main-input')!.onkeydown = (e: KeyboardEvent) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendMessage(state, vscode);
        }
    };

    document.querySelectorAll('.quick-action[data-prompt]').forEach(btn => {
        (btn as HTMLElement).onclick = () => {
            (document.getElementById('main-input') as HTMLTextAreaElement).value = (btn as HTMLElement).dataset.prompt || '';
            (document.getElementById('main-input') as HTMLTextAreaElement).focus();
        };
    });

    const stopBtn = document.getElementById('stop-btn') as HTMLButtonElement | null;
    if (stopBtn) {
        stopBtn.onclick = () => requestCancel(state, vscode);
    }
}

export function bindMessageEvents(state: ViewState, vscode: any): void {
    window.addEventListener('message', event => {
        const message = event.data;
        switch (message.command) {
            case 'askResponse':
                if (state.currentAssistantMsg) {
                    updateAssistantMessage(state.currentAssistantMsg, message.content, state.currentSources);
                }
                break;
            case 'sources':
                state.currentSources = message.sources;
                break;
            case 'status':
                if (state.currentAssistantMsg) {
                    updateWorkingStatus(state.currentAssistantMsg, message.status);
                }
                break;
            case 'planResponse':
                if (state.currentAssistantMsg) {
                    showPlanSteps(state, state.currentAssistantMsg, message.steps, message.workflowId, {
                        onRefine: (instruction) => {
                            if (instruction && state.currentWorkflowId) {
                                vscode.postMessage({ command: 'refinePlan', workflowId: state.currentWorkflowId, instruction });
                            }
                        },
                        onConfirm: () => {
                            if (state.currentWorkflowId) {
                                vscode.postMessage({ command: 'confirmPlan', workflowId: state.currentWorkflowId });
                            }
                        }
                    });
                }
                break;
            case 'planConfirmed':
                state.currentAssistantMsg = addAssistantMessage(state);
                break;
            case 'setMode':
                const modeEl = document.querySelector('[data-mode="' + message.mode + '"]') as HTMLElement | null;
                modeEl?.click();
                break;
            case 'codeStart':
                startCodeRun(state);
                break;
            case 'stepStart':
                if (state.currentAssistantMsg) {
                    const stepIndex = message.stepIndex;
                    state.activeStepIndex = stepIndex;
                    ensureStepBlock(state, stepIndex, message.step);
                    setStepStatus(state, stepIndex, '进行中');
                }
                break;
            case 'stepComplete':
                if (state.currentAssistantMsg) {
                    const stepIndex = message.stepIndex;
                    setStepStatus(state, stepIndex, '完成');
                }
                break;
            case 'thought':
                if (state.currentAssistantMsg) {
                    const container = getActiveEventContainer(state);
                    addAgentEvent(state.currentAssistantMsg, 'thought', message.content, container);
                }
                break;
            case 'action':
                if (state.currentAssistantMsg) {
                    const label = formatActionLabel(message.tool, message.input);
                    const milestoneContainer = getActiveMilestoneContainer(state);
                    state.lastActionMilestone = addMilestone(label, 'pending', milestoneContainer);
                    const container = getActiveEventContainer(state);
                    addAgentEvent(state.currentAssistantMsg, 'action', message.tool + ': ' + JSON.stringify(message.input), container);
                }
                break;
            case 'observation':
                if (state.currentAssistantMsg) {
                    let status = 'success';
                    if (typeof message.success === 'boolean') {
                        status = message.success ? 'success' : 'fail';
                    } else {
                        status = isFailureObservation(message.content) ? 'fail' : 'success';
                    }
                    updateMilestone(state.lastActionMilestone, status);
                    const container = getActiveEventContainer(state);
                    addAgentEvent(state.currentAssistantMsg, 'observation', message.content, container);
                    const milestoneContainer = getActiveMilestoneContainer(state);
                    maybeAddFileMilestone(state, message.content, milestoneContainer);
                }
                break;
            case 'codeResult':
                if (state.currentAssistantMsg) {
                    showFinalResult(state.currentAssistantMsg, message.answer);
                }
                state.codeRunHasFinal = true;
                finishCodeRun(state, '✅ 执行完成');
                state.currentSources = null;
                break;
            case 'codeComplete':
                if (!state.codeRunHasFinal && state.cancelRequested) {
                    finishCodeRun(state, '🛑 已取消');
                    setStopButtonState(true, '已取消');
                    setAllStepStatuses(state, '已取消', true);
                } else if (!state.codeRunHasFinal) {
                    finishCodeRun(state, '✅ 执行结束（无最终输出）');
                } else {
                    finishCodeRun(state, '✅ 执行完成');
                }
                state.currentSources = null;
                break;
            case 'codeCancelRequested':
                state.cancelRequested = true;
                updateCodeStatus(state, '取消中…');
                setStopButtonState(true, '取消中');
                setAllStepStatuses(state, '取消中', true);
                break;
            case 'codeCancelled':
                state.cancelRequested = true;
                finishCodeRun(state, '🛑 已取消');
                setStopButtonState(true, '已取消');
                addMilestone('任务已取消', 'success', getActiveMilestoneContainer(state));
                setAllStepStatuses(state, '已取消', true);
                state.currentSources = null;
                break;
            case 'error':
                if (state.currentAssistantMsg) {
                    state.currentAssistantMsg.querySelector('.message-content')!.innerHTML = '<div class="error">❌ ' + message.message + '</div>';
                }
                state.codeRunHasFinal = true;
                finishCodeRun(state, '❌ 执行失败');
                state.currentSources = null;
                break;
        }
    });
}

function sendMessage(state: ViewState, vscode: any): void {
    const input = document.getElementById('main-input') as HTMLTextAreaElement;
    const text = input.value.trim();
    if (!text) return;

    addUserMessage(state, text, vscode);
    state.currentAssistantMsg = addAssistantMessage(state);

    switch(state.currentMode) {
        case 'ask':
            vscode.postMessage({ command: 'ask', query: text });
            break;
        case 'agent':
            vscode.postMessage({ command: 'plan', task: text });
            break;
    }

    input.value = '';
}

function addUserMessage(state: ViewState, text: string, vscode: any): void {
    document.getElementById('welcome')?.classList.add('hidden');
    const container = document.getElementById('chat-container')!;
    const msg = document.createElement('div');
    msg.className = 'message message-user';
    msg.dataset.originalText = text;
    msg.innerHTML = '<div class="message-content">' + escapeHtml(text) + '</div>';

    const content = msg.querySelector('.message-content') as HTMLElement;
    content.onclick = () => enterEditMode(state, msg, vscode);

    container.appendChild(msg);
    scrollToBottom();
}

function enterEditMode(state: ViewState, msg: HTMLElement, vscode: any): void {
    const content = msg.querySelector('.message-content') as HTMLElement;
    if (content.classList.contains('editing')) return;

    const originalText = msg.dataset.originalText || '';
    content.classList.add('editing');
    content.innerHTML = `
        <textarea class="edit-textarea">${escapeHtml(originalText)}</textarea>
        <div class="edit-actions">
            <button class="edit-cancel">取消</button>
            <button class="edit-send">发送</button>
        </div>
    `;

    const textarea = content.querySelector('.edit-textarea') as HTMLTextAreaElement;
    textarea.focus();
    textarea.selectionStart = textarea.value.length;

    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
    textarea.oninput = () => {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    };

    (content.querySelector('.edit-cancel') as HTMLElement).onclick = (e) => {
        e.stopPropagation();
        exitEditMode(msg);
    };

    (content.querySelector('.edit-send') as HTMLElement).onclick = (e) => {
        e.stopPropagation();
        const newText = textarea.value.trim();
        if (newText) {
            resendFromMessage(state, msg, newText, vscode);
        }
    };

    textarea.onkeydown = (e: KeyboardEvent) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            const newText = textarea.value.trim();
            if (newText) {
                resendFromMessage(state, msg, newText, vscode);
            }
        }
        if (e.key === 'Escape') {
            exitEditMode(msg);
        }
    };

    textarea.onclick = (e) => e.stopPropagation();
}

function exitEditMode(msg: HTMLElement): void {
    const content = msg.querySelector('.message-content') as HTMLElement;
    content.classList.remove('editing');
    content.innerHTML = escapeHtml(msg.dataset.originalText || '');
    content.onclick = () => {};
}

function resendFromMessage(state: ViewState, msg: HTMLElement, newText: string, vscode: any): void {
    const container = document.getElementById('chat-container')!;
    let sibling = msg.nextElementSibling;
    while (sibling) {
        const next = sibling.nextElementSibling;
        container.removeChild(sibling);
        sibling = next;
    }

    msg.dataset.originalText = newText;
    const content = msg.querySelector('.message-content') as HTMLElement;
    content.classList.remove('editing');
    content.innerHTML = escapeHtml(newText);
    content.onclick = () => enterEditMode(state, msg, vscode);

    state.currentAssistantMsg = addAssistantMessage(state);
    state.currentSources = null;

    switch(state.currentMode) {
        case 'ask':
            vscode.postMessage({ command: 'ask', query: newText });
            break;
        case 'agent':
            vscode.postMessage({ command: 'plan', task: newText });
            break;
    }
}

function startCodeRun(state: ViewState): void {
    state.codeRunActive = true;
    state.cancelRequested = false;
    state.codeRunHasFinal = false;
    state.lastActionMilestone = null;
    state.activeStepIndex = null;
    state.stepEventContainers = {};
    state.stepMilestoneContainers = {};
    state.stepStatusLabels = {};
    if (state.currentAssistantMsg) {
        initCodeRunView(state, state.currentAssistantMsg);
    }
    state.codeRunStart = Date.now();
    updateCodeStatus(state, '执行中 · 已运行 0s');
    setStopButtonState(false, '停止执行');
    if (state.codeRunTimer) {
        clearInterval(state.codeRunTimer);
    }
    state.codeRunTimer = window.setInterval(() => {
        if (!state.codeRunActive) return;
        const elapsed = formatElapsed(Date.now() - state.codeRunStart);
        updateCodeStatus(state, '执行中 · 已运行 ' + elapsed);
    }, 1000);
}

function finishCodeRun(state: ViewState, statusText: string): void {
    state.codeRunActive = false;
    if (state.codeRunTimer) {
        clearInterval(state.codeRunTimer);
        state.codeRunTimer = null;
    }
    if (statusText) {
        updateCodeStatus(state, statusText);
    }
    setStopButtonState(true);
}

function requestCancel(state: ViewState, vscode: any): void {
    if (state.cancelRequested) return;
    state.cancelRequested = true;
    updateCodeStatus(state, '取消中…');
    setStopButtonState(true, '取消中');
    vscode.postMessage({ command: 'cancelCode' });
}

function isFailureObservation(content: string): boolean {
    if (!content) return false;
    const sanitized = content.replace(/ERROR:\s+QEMU System Power off: with GPIO\./gi, '');
    return /失败|error|异常/i.test(sanitized);
}

function formatActionLabel(tool: string, input: any): string {
    if (tool === 'file_write') {
        return '写入文件 ' + (input?.path || '');
    }
    if (tool === 'file_read') {
        return '读取文件 ' + (input?.path || '');
    }
    if (tool === 'ta_generator') {
        return '生成 TA ' + (input?.name || '');
    }
    if (tool === 'ca_generator') {
        return '生成 CA ' + (input?.name || '');
    }
    if (tool === 'crypto_helper') {
        return '生成加密片段 ' + (input?.operation || '');
    }
    return '执行工具 ' + tool;
}

function setupDropdown(dropdownId: string, menuId: string, onSelect: (item: HTMLElement) => void): void {
    const dropdown = document.getElementById(dropdownId) as HTMLElement;
    const menu = document.getElementById(menuId) as HTMLElement;
    dropdown.querySelector('.selector')!.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelectorAll('.dropdown-menu').forEach(m => m !== menu && m.classList.remove('show'));
        menu.classList.toggle('show');
    });
    menu.querySelectorAll('.dropdown-item').forEach(item => {
        (item as HTMLElement).onclick = () => {
            menu.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            menu.classList.remove('show');
            onSelect(item as HTMLElement);
        };
    });
}
