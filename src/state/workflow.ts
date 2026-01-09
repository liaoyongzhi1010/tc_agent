import * as vscode from 'vscode';
import { Workflow } from '../agent/types';

export class WorkflowState {
  private workflows: Map<string, Workflow> = new Map();
  private currentWorkflow: Workflow | null = null;
  private context: vscode.ExtensionContext;
  private readonly STORAGE_KEY = 'tcAgent.workflows';

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    this.loadFromStorage();
  }

  setCurrentWorkflow(workflow: Workflow): void {
    this.currentWorkflow = workflow;
    this.workflows.set(workflow.id, workflow);
    this.saveToStorage();
  }

  getCurrentWorkflow(): Workflow | null {
    return this.currentWorkflow;
  }

  updateWorkflow(workflow: Workflow): void {
    this.workflows.set(workflow.id, workflow);
    if (this.currentWorkflow && this.currentWorkflow.id === workflow.id) {
      this.currentWorkflow = workflow;
    }
    this.saveToStorage();
  }

  getWorkflow(id: string): Workflow | undefined {
    return this.workflows.get(id);
  }

  getAllWorkflows(): Workflow[] {
    return Array.from(this.workflows.values());
  }

  clearCurrent(): void {
    this.currentWorkflow = null;
    this.saveToStorage();
  }

  private loadFromStorage(): void {
    const stored = this.context.globalState.get<Array<[string, Workflow]>>(this.STORAGE_KEY);
    if (stored) {
      this.workflows = new Map(stored);
    }
  }

  private saveToStorage(): void {
    const data = Array.from(this.workflows.entries());
    this.context.globalState.update(this.STORAGE_KEY, data);
  }
}
