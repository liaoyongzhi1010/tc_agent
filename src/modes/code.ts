import { IAgentClient, TaskRequest, Workflow, WorkflowStep } from '../agent/types';
import { WorkflowState } from '../state';
import { logger } from '../utils';

export class CodeMode {
  constructor(
    private agentClient: IAgentClient,
    private workflowState: WorkflowState
  ) {}

  async executeWorkflow(workflow: Workflow): Promise<void> {
    try {
      logger.info(`Starting workflow execution: ${workflow.id}`);

      // Update workflow status
      workflow.status = 'running';
      this.workflowState.updateWorkflow(workflow);

      // Execute each step
      for (const step of workflow.steps) {
        await this.executeStep(workflow, step);
      }

      // Mark workflow as completed
      workflow.status = 'completed';
      this.workflowState.updateWorkflow(workflow);

      logger.info(`Workflow ${workflow.id} completed successfully`);
    } catch (error) {
      workflow.status = 'failed';
      this.workflowState.updateWorkflow(workflow);
      logger.error(`Workflow ${workflow.id} failed`, error);
      throw error;
    }
  }

  private async executeStep(workflow: Workflow, step: WorkflowStep): Promise<void> {
    try {
      logger.info(`Executing step: ${step.id} - ${step.tool}`);

      // Update step status
      step.status = 'running';
      this.workflowState.updateWorkflow(workflow);

      // Send execution request to agent
      const request: TaskRequest = {
        mode: 'code',
        message: `Execute step: ${step.tool}`,
        context: {
          workflow,
        },
      };

      const response = await this.agentClient.sendTask(request);

      if (!response.success) {
        throw new Error(response.error || 'Step execution failed');
      }

      // Update step with results
      step.status = 'success';
      step.output = response.message || '';
      this.workflowState.updateWorkflow(workflow);

      logger.info(`Step ${step.id} completed successfully`);
    } catch (error) {
      step.status = 'failed';
      step.error = error instanceof Error ? error.message : String(error);
      this.workflowState.updateWorkflow(workflow);
      throw error;
    }
  }

  getCurrentWorkflow(): Workflow | null {
    return this.workflowState.getCurrentWorkflow();
  }
}
