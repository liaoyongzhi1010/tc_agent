/**
 * API客户端 - 与后端通信
 */

import { BackendManager } from './BackendManager';

export interface AskRequest {
    query: string;
    knowledge_type?: string;
    model?: string;
}

export interface AskResponse {
    answer: string;
    sources: Array<{ source: string; score: number }>;
}

export interface PlanStep {
    id: string;
    description: string;
    status: string;
    sub_steps?: PlanStep[];
}

export interface PlanResponse {
    workflow_id: string;
    task?: string;
    steps: PlanStep[];
}

export class ApiClient {
    constructor(private backendManager: BackendManager) {}

    private getBaseUrl(): string {
        return this.backendManager.getBaseUrl();
    }

    async ask(request: AskRequest): Promise<AskResponse> {
        const response = await fetch(`${this.getBaseUrl()}/ask/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            throw new Error(`Ask failed: ${response.statusText}`);
        }

        return response.json() as Promise<AskResponse>;
    }

    async *askStream(request: AskRequest): AsyncGenerator<{ type: string; data: any }> {
        const response = await fetch(`${this.getBaseUrl()}/ask/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            throw new Error(`Ask stream failed: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        yield data;
                    } catch (e) {
                        console.error('Failed to parse SSE data:', line);
                    }
                }
            }
        }
    }

    async initPlan(task: string): Promise<PlanResponse> {
        const response = await fetch(`${this.getBaseUrl()}/plan/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task })
        });

        if (!response.ok) {
            throw new Error(`Init plan failed: ${response.statusText}`);
        }

        return response.json() as Promise<PlanResponse>;
    }

    async refinePlan(workflowId: string, instruction: string): Promise<PlanResponse> {
        const response = await fetch(`${this.getBaseUrl()}/plan/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workflow_id: workflowId, instruction })
        });

        if (!response.ok) {
            throw new Error(`Refine plan failed: ${response.statusText}`);
        }

        return response.json() as Promise<PlanResponse>;
    }

    async confirmPlan(workflowId: string): Promise<any> {
        const response = await fetch(`${this.getBaseUrl()}/plan/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workflow_id: workflowId })
        });

        if (!response.ok) {
            throw new Error(`Confirm plan failed: ${response.statusText}`);
        }

        return response.json();
    }

    createCodeWebSocket(workflowId: string): WebSocket {
        const wsUrl = this.getBaseUrl().replace('http', 'ws');
        return new WebSocket(`${wsUrl}/code/execute/${workflowId}`);
    }

    async *executeDirectStream(task: string): AsyncGenerator<{ type: string; data: any }> {
        const response = await fetch(`${this.getBaseUrl()}/code/execute-direct`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task })
        });

        if (!response.ok) {
            throw new Error(`Execute failed: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        yield data;
                    } catch (e) {
                        console.error('Failed to parse SSE data:', line);
                    }
                }
            }
        }
    }

    async getTools(): Promise<Array<{ name: string; description: string; schema: any }>> {
        const response = await fetch(`${this.getBaseUrl()}/code/tools`);
        if (!response.ok) {
            throw new Error(`Get tools failed: ${response.statusText}`);
        }
        const data = await response.json() as { tools: Array<{ name: string; description: string; schema: any }> };
        return data.tools;
    }

    async healthCheck(): Promise<boolean> {
        try {
            const response = await fetch(`${this.getBaseUrl()}/health`);
            return response.ok;
        } catch {
            return false;
        }
    }
}
