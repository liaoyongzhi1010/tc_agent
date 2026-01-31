import { createState } from './state';
import { bindDomEvents, bindMessageEvents } from './events';

declare function acquireVsCodeApi(): any;

const vscode = acquireVsCodeApi();
const state = createState();

bindDomEvents(state, vscode);
bindMessageEvents(state, vscode);
