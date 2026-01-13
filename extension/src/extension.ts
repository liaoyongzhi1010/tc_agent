/**
 * TC Agent VS Code Extension
 * 可信计算开发助手
 */

import * as vscode from 'vscode';
import { BackendManager } from './services/BackendManager';
import { MainViewProvider } from './views/MainViewProvider';

let backendManager: BackendManager;

export async function activate(context: vscode.ExtensionContext) {
    console.log('TC Agent is activating...');

    // 启动Python后端
    backendManager = new BackendManager(context);

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
