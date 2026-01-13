/**
 * 代码编辑服务 - 使用WorkspaceEdit API修改代码
 */

import * as vscode from 'vscode';

export interface FileEdit {
    path: string;
    content: string;
    action: 'create' | 'modify' | 'delete';
}

export class WorkspaceEditor {

    async applyEdits(edits: FileEdit[]): Promise<boolean> {
        const workspaceEdit = new vscode.WorkspaceEdit();

        for (const edit of edits) {
            const uri = vscode.Uri.file(edit.path);

            switch (edit.action) {
                case 'create':
                    workspaceEdit.createFile(uri, { overwrite: true });
                    workspaceEdit.insert(uri, new vscode.Position(0, 0), edit.content);
                    break;

                case 'modify':
                    try {
                        const document = await vscode.workspace.openTextDocument(uri);
                        const fullRange = new vscode.Range(
                            document.positionAt(0),
                            document.positionAt(document.getText().length)
                        );
                        workspaceEdit.replace(uri, fullRange, edit.content);
                    } catch (error) {
                        // 文件不存在,创建新文件
                        workspaceEdit.createFile(uri, { overwrite: true });
                        workspaceEdit.insert(uri, new vscode.Position(0, 0), edit.content);
                    }
                    break;

                case 'delete':
                    workspaceEdit.deleteFile(uri);
                    break;
            }
        }

        const success = await vscode.workspace.applyEdit(workspaceEdit);
        if (!success) {
            vscode.window.showErrorMessage('Failed to apply workspace edits');
        }
        return success;
    }

    async createFile(path: string, content: string): Promise<boolean> {
        return this.applyEdits([{ path, content, action: 'create' }]);
    }

    async modifyFile(path: string, content: string): Promise<boolean> {
        return this.applyEdits([{ path, content, action: 'modify' }]);
    }

    async deleteFile(path: string): Promise<boolean> {
        return this.applyEdits([{ path, content: '', action: 'delete' }]);
    }

    async showDiff(originalPath: string, newContent: string): Promise<void> {
        const originalUri = vscode.Uri.file(originalPath);

        // 创建临时文档显示新内容
        const newDoc = await vscode.workspace.openTextDocument({
            content: newContent,
            language: this.getLanguageId(originalPath)
        });

        await vscode.commands.executeCommand(
            'vscode.diff',
            originalUri,
            newDoc.uri,
            `${originalPath} (修改预览)`
        );
    }

    async openFile(path: string): Promise<void> {
        const uri = vscode.Uri.file(path);
        const document = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(document);
    }

    private getLanguageId(path: string): string {
        const ext = path.split('.').pop()?.toLowerCase();
        const langMap: { [key: string]: string } = {
            'c': 'c',
            'h': 'c',
            'py': 'python',
            'ts': 'typescript',
            'js': 'javascript',
            'json': 'json',
            'md': 'markdown',
            'mk': 'makefile',
        };
        return langMap[ext || ''] || 'plaintext';
    }
}
