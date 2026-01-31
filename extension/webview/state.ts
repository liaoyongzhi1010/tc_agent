export type Mode = 'ask' | 'agent';

export interface ViewState {
    currentMode: Mode;
    currentModel: string;
    currentWorkflowId: string | null;
    currentAssistantMsg: HTMLElement | null;
    totalSteps: number;
    completedSteps: number;
    codeRunTimer: number | null;
    codeRunStart: number;
    codeRunActive: boolean;
    codeRunHasFinal: boolean;
    currentCodeStatus: string;
    cancelRequested: boolean;
    lastActionMilestone: HTMLElement | null;
    activeStepIndex: number | null;
    stepEventContainers: Record<number, HTMLElement>;
    stepMilestoneContainers: Record<number, HTMLElement>;
    stepStatusLabels: Record<number, HTMLElement>;
    currentSources: any;
}

export function createState(): ViewState {
    return {
        currentMode: 'ask',
        currentModel: 'qwen',
        currentWorkflowId: null,
        currentAssistantMsg: null,
        totalSteps: 0,
        completedSteps: 0,
        codeRunTimer: null,
        codeRunStart: 0,
        codeRunActive: false,
        codeRunHasFinal: false,
        currentCodeStatus: '',
        cancelRequested: false,
        lastActionMilestone: null,
        activeStepIndex: null,
        stepEventContainers: {},
        stepMilestoneContainers: {},
        stepStatusLabels: {},
        currentSources: null
    };
}
