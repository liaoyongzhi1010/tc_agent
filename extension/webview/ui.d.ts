import { ViewState } from './state';
export declare function escapeHtml(text: string): string;
export declare function scrollToBottom(): void;
export declare function highlightCode(code: string, lang: string): string;
export declare function renderMarkdown(text: string): string;
export declare function addAssistantMessage(state: ViewState, statusText?: string): HTMLElement;
export declare function updateWorkingStatus(msg: HTMLElement, statusText: string): void;
export declare function updateAssistantMessage(msg: HTMLElement, content: string, sources?: any[] | null): void;
export declare function addAgentEvent(msg: HTMLElement, type: string, content: any, containerOverride?: HTMLElement | null): void;
export declare function addMilestone(text: string, status: string, containerOverride?: HTMLElement | null): HTMLElement;
export declare function updateMilestone(item: HTMLElement | null, status: string): void;
export declare function initCodeRunView(state: ViewState, msg: HTMLElement): void;
export declare function updateCodeStatus(state: ViewState, statusText: string): void;
export declare function setStopButtonState(enabled: boolean, label?: string): void;
export declare function ensureStepBlock(state: ViewState, stepIndex: number, step: any): void;
export declare function setStepStatus(state: ViewState, stepIndex: number, statusText: string): void;
export declare function setAllStepStatuses(state: ViewState, statusText: string, onlyInProgress?: boolean): void;
export declare function showFinalResult(msg: HTMLElement, answer: string): void;
export declare function showPlanSteps(state: ViewState, msg: HTMLElement, steps: any[], workflowId: string, handlers: {
    onRefine: (instruction: string) => void;
    onConfirm: () => void;
}): void;
export declare function getActiveMilestoneContainer(state: ViewState): HTMLElement | null;
export declare function getActiveEventContainer(state: ViewState): HTMLElement | null;
export declare function maybeAddFileMilestone(state: ViewState, content: string, containerOverride?: HTMLElement | null): void;
export declare function formatElapsed(ms: number): string;
//# sourceMappingURL=ui.d.ts.map