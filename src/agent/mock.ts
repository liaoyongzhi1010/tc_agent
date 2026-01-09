import { IAgentClient, TaskRequest, TaskResponse, WSMessage, Workflow } from './types';

// Mock Agent Client for development without backend
export class MockAgentClient implements IAgentClient {
  private messageCallbacks: Array<(message: WSMessage) => void> = [];
  private connected: boolean = false;

  async connect(): Promise<void> {
    this.connected = true;
    console.log('[Mock] Agent connected');
  }

  disconnect(): void {
    this.connected = false;
    console.log('[Mock] Agent disconnected');
  }

  async sendTask(request: TaskRequest): Promise<TaskResponse> {
    console.log('[Mock] Received task:', request);

    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 500));

    if (request.mode === 'ask') {
      return {
        success: true,
        message: `这是一个 Mock 响应。你的问题是: "${request.message}"\n\n` +
                 `OP-TEE 是基于 ARM TrustZone 技术的开源可信执行环境实现。` +
                 `它提供了安全世界（Secure World）和普通世界（Normal World）的隔离。`,
      };
    }

    if (request.mode === 'plan') {
      const mockWorkflow: Workflow = {
        id: `wf-${Date.now()}`,
        name: '示例 Workflow',
        status: 'draft',
        steps: [
          {
            id: 'step-1',
            tool: 'code_gen',
            params: { template: 'basic_ta', output: './ta' },
            status: 'pending',
          },
          {
            id: 'step-2',
            tool: 'build_ta',
            params: { ta_path: './ta' },
            status: 'pending',
          },
        ],
      };

      // Simulate sending workflow via WebSocket
      setTimeout(() => {
        this.messageCallbacks.forEach(cb => cb({
          type: 'workflow',
          payload: mockWorkflow,
        }));
      }, 100);

      return {
        success: true,
        message: '已生成 Workflow，请查看并确认',
        workflow: mockWorkflow,
      };
    }

    return {
      success: true,
      message: `${request.mode} 模式功能开发中...`,
    };
  }

  onMessage(callback: (message: WSMessage) => void): void {
    this.messageCallbacks.push(callback);
  }

  isConnected(): boolean {
    return this.connected;
  }
}
