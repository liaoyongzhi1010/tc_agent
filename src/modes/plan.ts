import { IAgentClient, TaskRequest, TaskResponse, Workflow } from '../agent/types';
import { ConversationState, WorkflowState } from '../state';
import { logger } from '../utils';

export class PlanMode {
  constructor(
    private agentClient: IAgentClient,
    private conversationState: ConversationState,
    private workflowState: WorkflowState
  ) {}

  async handleMessage(message: string): Promise<{ reply: string; workflow?: Workflow }> {
    try {
      // Add user message to history
      this.conversationState.addMessage({
        role: 'user',
        content: message,
        timestamp: Date.now(),
      });

      // Prepare request with current workflow if exists
      const currentWorkflow = this.workflowState.getCurrentWorkflow();
      const request: TaskRequest = {
        mode: 'plan',
        message,
        context: {
          workflow: currentWorkflow || undefined,
          history: this.conversationState.getRecentMessages(10),
        },
      };

      // Send to agent
      const response: TaskResponse = await this.agentClient.sendTask(request);

      if (!response.success) {
        throw new Error(response.error || 'Task failed');
      }

      const replyMessage = response.message || '无响应';

      // Add assistant message to history
      this.conversationState.addMessage({
        role: 'assistant',
        content: replyMessage,
        timestamp: Date.now(),
      });

      // Update workflow if provided
      if (response.workflow) {
        this.workflowState.setCurrentWorkflow(response.workflow);
      }

      return {
        reply: replyMessage,
        workflow: response.workflow,
      };
    } catch (error) {
      logger.error('PLAN mode error', error);
      throw error;
    }
  }

  confirmWorkflow(): Workflow | null {
    const workflow = this.workflowState.getCurrentWorkflow();
    if (!workflow) {
      return null;
    }

    // Update workflow status to confirmed
    const confirmedWorkflow: Workflow = {
      ...workflow,
      status: 'confirmed',
    };

    this.workflowState.updateWorkflow(confirmedWorkflow);
    logger.info(`Workflow ${workflow.id} confirmed`);

    return confirmedWorkflow;
  }

  getCurrentWorkflow(): Workflow | null {
    return this.workflowState.getCurrentWorkflow();
  }
}
