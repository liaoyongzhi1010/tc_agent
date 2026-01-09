import axios, { AxiosInstance } from 'axios';
import WebSocket from 'ws';
import { IAgentClient, TaskRequest, TaskResponse, WSMessage } from './types';
import { logger } from '../utils';

export class AgentClient implements IAgentClient {
  private httpClient: AxiosInstance;
  private ws: WebSocket | null = null;
  private wsUrl: string;
  private messageCallbacks: Array<(message: WSMessage) => void> = [];
  private reconnectTimer: NodeJS.Timeout | null = null;
  private shouldReconnect: boolean = true;

  constructor(serverUrl: string, wsUrl: string) {
    this.httpClient = axios.create({
      baseURL: serverUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    this.wsUrl = wsUrl;
  }

  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.wsUrl);

        this.ws.on('open', () => {
          logger.info('WebSocket connected');
          this.shouldReconnect = true;
          resolve();
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          try {
            const message: WSMessage = JSON.parse(data.toString());
            this.messageCallbacks.forEach(callback => callback(message));
          } catch (error) {
            logger.error('Failed to parse WebSocket message', error);
          }
        });

        this.ws.on('error', (error) => {
          logger.error('WebSocket error', error);
          reject(error);
        });

        this.ws.on('close', () => {
          logger.info('WebSocket closed');
          if (this.shouldReconnect) {
            this.scheduleReconnect();
          }
        });
      } catch (error) {
        logger.error('Failed to create WebSocket connection', error);
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  async sendTask(request: TaskRequest): Promise<TaskResponse> {
    try {
      logger.info(`Sending task: ${request.mode} - ${request.message}`);
      const response = await this.httpClient.post<TaskResponse>('/api/task', request);
      return response.data;
    } catch (error) {
      logger.error('Failed to send task', error);
      throw error;
    }
  }

  onMessage(callback: (message: WSMessage) => void): void {
    this.messageCallbacks.push(callback);
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      logger.info('Attempting to reconnect WebSocket...');
      this.connect().catch(error => {
        logger.error('Reconnection failed', error);
      });
    }, 5000);
  }
}
