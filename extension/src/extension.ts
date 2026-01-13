/**
 * TC Agent VS Code Extension
 * 可信计算开发助手
 */

import * as vscode from 'vscode';
import { BackendManager } from './services/BackendManager';
import { MainViewProvider } from './views/MainViewProvider';
import { ApiClient } from './services/ApiClient';

let backendManager: BackendManager;
let apiClient: ApiClient;

export async function activate(context: vscode.ExtensionContext) {
    console.log('TC Agent is activating...');

    // 启动Python后端
    backendManager = new BackendManager(context);
    apiClient = new ApiClient(backendManager);

    // 注册主视图
    const mainViewProvider = new MainViewProvider(context, backendManager);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'tcAgent.mainView',
            mainViewProvider
        )
    );

    // 注册命令
    context.subscriptions.push(
        vscode.commands.registerCommand('tcAgent.ask', () => {
            mainViewProvider.switchMode('ask');
            vscode.commands.executeCommand('tcAgent.mainView.focus');
        }),
        vscode.commands.registerCommand('tcAgent.plan', () => {
            mainViewProvider.switchMode('plan');
            vscode.commands.executeCommand('tcAgent.mainView.focus');
        }),
        vscode.commands.registerCommand('tcAgent.code', () => {
            mainViewProvider.switchMode('code');
            vscode.commands.executeCommand('tcAgent.mainView.focus');
        }),
        vscode.commands.registerCommand('tcAgent.switchModel', async () => {
            const models = ['qwen', 'zhipu', 'doubao'];
            const selected = await vscode.window.showQuickPick(models, {
                placeHolder: '选择LLM模型'
            });
            if (selected) {
                const config = vscode.workspace.getConfiguration('tcAgent');
                await config.update('llm.provider', selected, true);
                vscode.window.showInformationMessage(`已切换到 ${selected}`);
            }
        }),
        vscode.commands.registerCommand('tcAgent.startBackend', async () => {
            try {
                await backendManager.start();
                vscode.window.showInformationMessage('TC Agent 后端已启动');
            } catch (error) {
                vscode.window.showErrorMessage(`启动失败: ${error}`);
            }
        }),
        vscode.commands.registerCommand('tcAgent.stopBackend', () => {
            backendManager.stop();
            vscode.window.showInformationMessage('TC Agent 后端已停止');
        }),
        vscode.commands.registerCommand('tcAgent.addToKnowledge', async (uri?: vscode.Uri) => {
            try {
                // 获取文件路径
                let filePath: string | undefined;

                if (uri) {
                    // 从资源管理器右键菜单
                    filePath = uri.fsPath;
                } else {
                    // 从编辑器
                    const editor = vscode.window.activeTextEditor;
                    if (editor) {
                        filePath = editor.document.uri.fsPath;
                    }
                }

                if (!filePath) {
                    vscode.window.showWarningMessage('请选择要添加的文件');
                    return;
                }

                // 选择知识库类型
                const collectionType = await vscode.window.showQuickPick(
                    [
                        { label: '代码知识库', value: 'code', description: '用于代码相关问答' },
                        { label: '文档知识库', value: 'text', description: '用于文档相关问答' }
                    ],
                    { placeHolder: '选择知识库类型' }
                );

                if (!collectionType) {
                    return;
                }

                // 调用后端API添加文件
                const baseUrl = backendManager.getBaseUrl();
                const response = await fetch(`${baseUrl}/knowledge/add-directory`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        path: filePath,
                        collection: collectionType.value,
                        file_patterns: ['*']
                    })
                });

                if (response.ok) {
                    const data = await response.json() as { documents_added?: number };
                    vscode.window.showInformationMessage(
                        `已添加到${collectionType.label}，共 ${data.documents_added || 1} 个文档`
                    );
                } else {
                    throw new Error(`API请求失败: ${response.statusText}`);
                }
            } catch (error) {
                vscode.window.showErrorMessage(`添加到知识库失败: ${error}`);
            }
        }),
        vscode.commands.registerCommand('tcAgent.showBackendLog', () => {
            backendManager.showOutput();
        })
    );

    // 自动启动后端
    try {
        await backendManager.start();
        console.log('TC Agent backend started');
    } catch (error) {
        console.error('Failed to start backend:', error);
        vscode.window.showWarningMessage(
            'TC Agent 后端启动失败，请检查Python环境配置'
        );
    }

    console.log('TC Agent is now active!');
}

export function deactivate() {
    console.log('TC Agent is deactivating...');
    backendManager?.stop();
}
