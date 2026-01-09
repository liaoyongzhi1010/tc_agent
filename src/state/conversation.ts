import * as vscode from 'vscode';
import { Message } from '../agent/types';

export class ConversationState {
  private messages: Message[] = [];
  private context: vscode.ExtensionContext;
  private readonly STORAGE_KEY = 'tcAgent.conversation';

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    this.loadFromStorage();
  }

  addMessage(message: Message): void {
    this.messages.push(message);
    this.saveToStorage();
  }

  getMessages(): Message[] {
    return [...this.messages];
  }

  getRecentMessages(count: number = 10): Message[] {
    return this.messages.slice(-count);
  }

  clear(): void {
    this.messages = [];
    this.saveToStorage();
  }

  private loadFromStorage(): void {
    const stored = this.context.globalState.get<Message[]>(this.STORAGE_KEY);
    if (stored) {
      this.messages = stored;
    }
  }

  private saveToStorage(): void {
    this.context.globalState.update(this.STORAGE_KEY, this.messages);
  }
}
