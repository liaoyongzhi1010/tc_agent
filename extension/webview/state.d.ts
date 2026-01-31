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
export declare function createState(): ViewState;
//# sourceMappingURL=state.d.ts.map