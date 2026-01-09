import * as vscode from 'vscode';
import { MockAgentClient, AgentClient, IAgentClient } from './agent';
import { ConversationState, WorkflowState } from './state';
import { ChatViewProvider } from './ui/chat';
import { logger, Config } from './utils';

let agentClient: IAgentClient;
let conversationState: ConversationState;
let workflowState: WorkflowState;

export async function activate(context: vscode.ExtensionContext) {
  logger.info('TC Agent extension is now active');

  // Initialize states
  conversationState = new ConversationState(context);
  workflowState = new WorkflowState(context);

  // Initialize agent client (use Mock for development)
  // TODO: Switch to real AgentClient when backend is ready
  const useMock = true; // Set to false to use real backend

  if (useMock) {
    agentClient = new MockAgentClient();
    logger.info('Using Mock Agent Client');
  } else {
    agentClient = new AgentClient(Config.serverUrl, Config.wsUrl);
    logger.info(`Using Real Agent Client: ${Config.serverUrl}`);
  }

  // Connect to agent
  try {
    await agentClient.connect();
    logger.info('Agent client connected');
  } catch (error) {
    logger.error('Failed to connect to agent', error);
    vscode.window.showErrorMessage('Failed to connect to TC Agent backend');
  }

  // Register Chat View Provider
  const chatViewProvider = new ChatViewProvider(
    context.extensionUri,
    agentClient,
    conversationState,
    workflowState
  );

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      ChatViewProvider.viewType,
      chatViewProvider
    )
  );

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('tcAgent.openChat', () => {
      vscode.commands.executeCommand('tcAgent.chatView.focus');
    })
  );

  // Listen to WebSocket messages
  agentClient.onMessage((message) => {
    logger.info(`Received WebSocket message: ${message.type}`);
    // Handle real-time updates from agent
    switch (message.type) {
      case 'workflow':
        workflowState.setCurrentWorkflow(message.payload);
        break;
      case 'log':
        logger.info(`Agent log: ${message.payload}`);
        break;
      case 'status':
        logger.info(`Agent status: ${message.payload}`);
        break;
    }
  });

  // Show welcome message
  vscode.window.showInformationMessage(
    'TC Agent 已启动！使用命令 "TC Agent: Open Chat" 打开聊天界面'
  );
}

export function deactivate() {
  logger.info('TC Agent extension is now deactivated');
  if (agentClient) {
    agentClient.disconnect();
  }
}
