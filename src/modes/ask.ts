import { IAgentClient, TaskRequest, TaskResponse } from '../agent/types';
import { ConversationState } from '../state';
import { logger } from '../utils';

export class AskMode {
  constructor(
    private agentClient: IAgentClient,
    private conversationState: ConversationState
  ) {}

  async handleMessage(message: string): Promise<string> {
    try {
      // Add user message to history
      this.conversationState.addMessage({
        role: 'user',
        content: message,
        timestamp: Date.now(),
      });

      // Prepare request
      const request: TaskRequest = {
        mode: 'ask',
        message,
        context: {
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

      return replyMessage;
    } catch (error) {
      logger.error('ASK mode error', error);
      throw error;
    }
  }
}
