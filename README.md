# TC Agent

一个用于 OP-TEE 和 Keystone TEE 开发的 VSCode 插件。

## 功能特性

- **智能对话**：通过聊天界面与 AI 助手交互
- **多种模式**：支持 Ask、Plan、Code 三种工作模式
- **实时通信**：基于 WebSocket 的实时双向通信
- **TEE 开发支持**：针对 Trusted Execution Environment 开发优化

## 安装

1. 克隆项目：
```bash
git clone <repository-url>
cd tc_agent
```

2. 安装依赖：
```bash
npm install
```

3. 编译项目：
```bash
npm run compile
```

4. 在 VSCode 中按 F5 启动调试

## 配置

在 VSCode 设置中可以配置以下选项：

- `tcAgent.serverUrl`：Agent 服务器地址（默认：`http://localhost:8000`）
- `tcAgent.wsUrl`：WebSocket 地址（默认：`ws://localhost:8000/ws`）
- `tcAgent.defaultMode`：默认工作模式（ask/plan/code）

## 使用

1. 点击活动栏的 TC Agent 图标打开聊天界面
2. 或使用命令面板 `TC Agent: Open Chat`
3. 在聊天界面中与 AI 助手交互

## 开发

```bash
# 监听文件变化自动编译
npm run watch

# 运行 Lint
npm run lint

# 打包插件
npm run package
```

## License

MIT