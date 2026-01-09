// 工作模式
export type Mode = 'ask' | 'plan' | 'code';

// 消息类型
export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

// Workflow 相关类型
export type WorkflowStatus = 'draft' | 'confirmed' | 'running' | 'completed' | 'failed';
export type StepStatus = 'pending' | 'running' | 'success' | 'failed';

export interface WorkflowStep {
  id: string;
  tool: string;
  params: Record<string, any>;
  status: StepStatus;
  output?: string;
  error?: string;
}

export interface Workflow {
  id: string;
  name: string;
  steps: WorkflowStep[];
  status: WorkflowStatus;
}

// 任务上下文
export interface TaskContext {
  files?: string[];
  workflow?: Workflow;
  history?: Message[];
}

// 任务请求
export interface TaskRequest {
  mode: Mode;
  message: string;
  context?: TaskContext;
}

// 任务响应
export interface TaskResponse {
  success: boolean;
  message?: string;
  workflow?: Workflow;
  error?: string;
}

// WebSocket 消息类型
export type WSMessageType = 'workflow' | 'log' | 'status' | 'chunk';

export interface WSMessage {
  type: WSMessageType;
  payload: any;
}

// Agent 客户端接口
export interface IAgentClient {
  connect(): Promise<void>;
  disconnect(): void;
  sendTask(request: TaskRequest): Promise<TaskResponse>;
  onMessage(callback: (message: WSMessage) => void): void;
  isConnected(): boolean;
}
