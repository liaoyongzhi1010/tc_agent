/**
 * 后端配置管理
 */

import * as vscode from 'vscode';
export class BackendManager {
    constructor() {}

    private getBackendUrl(): string | undefined {
        const config = vscode.workspace.getConfiguration('tcAgent');
        const raw = (config.get<string>('backendUrl') || '').trim();
        if (!raw) {
            return undefined;
        }
        // 允许用户只填 host:port
        if (!raw.startsWith('http://') && !raw.startsWith('https://')) {
            return `http://${raw}`;
        }
        return raw;
    }

    getBaseUrl(): string {
        const backendUrl = this.getBackendUrl();
        if (!backendUrl) {
            throw new Error('未配置 tcAgent.backendUrl');
        }
        return backendUrl.replace(/\/+$/, '');
    }
}
