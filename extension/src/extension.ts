/**
 * TC Agent VS Code Extension
 * 可信计算开发助手
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { TextDecoder } from 'util';
import { BackendManager } from './services/BackendManager';
import { MainViewProvider } from './views/MainViewProvider';

let backendManager: BackendManager;

export async function activate(context: vscode.ExtensionContext) {
    console.log('TC Agent is activating...');

    // 后端配置
    backendManager = new BackendManager();

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
        vscode.commands.registerCommand('tcAgent.agent', () => {
            mainViewProvider.switchMode('agent');
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

                const baseUrl = backendManager.getBaseUrl();

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

                const bytes = await vscode.workspace.fs.readFile(vscode.Uri.file(filePath));
                const maxSize = 1024 * 1024;
                if (bytes.byteLength > maxSize) {
                    vscode.window.showWarningMessage('文件过大(>1MB)，请拆分后再添加');
                    return;
                }

                const content = new TextDecoder('utf-8').decode(bytes);
                if (!content.trim()) {
                    vscode.window.showWarningMessage('文件内容为空，无法添加');
                    return;
                }

                const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
                const relative = workspaceRoot ? vscode.workspace.asRelativePath(filePath) : filePath;

                const response = await fetch(`${baseUrl}/knowledge/add-document`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content,
                        collection: collectionType.value,
                        metadata: {
                            source: relative,
                            filename: path.basename(filePath)
                        }
                    })
                });

                if (response.ok) {
                    vscode.window.showInformationMessage(
                        `已添加到${collectionType.label}`
                    );
                } else {
                    throw new Error(`API请求失败: ${response.statusText}`);
                }
            } catch (error) {
                vscode.window.showErrorMessage(`添加到知识库失败: ${error}`);
            }
        })
    );

    // 不再自动启动后端：由用户配置 backendUrl
    const config = vscode.workspace.getConfiguration('tcAgent');
    const backendUrl = (config.get<string>('backendUrl') || '').trim();
    if (!backendUrl) {
        vscode.window.showWarningMessage(
            '未配置 TC Agent 后端地址，请在设置中填写 tcAgent.backendUrl'
        );
    }

    console.log('TC Agent is now active!');
}

export function deactivate() {
    console.log('TC Agent is deactivating...');
}
