# TC Agent - 可信计算开发助手

基于 VS Code 的可信计算 (Trusted Computing) 开发助手插件，类似于 GitHub Copilot，专注于 OP-TEE/TrustZone 等可信计算领域的开发辅助。

## 功能特性

### 两种工作模式

1. **Ask 模式** - 基于 RAG 的智能问答
   - 支持纯文本知识库和代码知识库
   - 使用 Small-to-Big Retrieval 策略

2. **Agent 模式** - 规划 + 执行一体化
   - 为用户任务生成结构化 Workflow
   - 支持对话式迭代修改
   - 确认后自动执行（思考 → 行动 → 观察）
   - 实时代码修改与反馈

### 可信计算专用工具

- TA/CA 代码框架生成器
- 加密操作代码生成 (HMAC/AES/RSA)

**可选：Runner 工具包**
- OP-TEE Docker 编译与 QEMU 执行（需后端开启 `TC_AGENT_TOOL_PACKS=core,runner`）
- 如果后端没有 Docker 权限/镜像或只做问答，可不启用

### 支持的大模型

- 通义千问 (Qwen)
- 智谱 (GLM)
- 豆包 (Doubao)

## 项目结构

```
tc_agent/
├── extension/          # VS Code 插件 (TypeScript)
│   ├── src/
│   │   ├── extension.ts
│   │   ├── views/
│   │   └── services/
│   └── package.json
│
├── backend/            # Python 后端 (FastAPI)
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── tools/
│   │   └── infrastructure/
│   └── requirements.txt
│
└── docs/
    └── plans/
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- VS Code 1.85+

### 安装步骤

1. **安装 Python 依赖**

```bash
cd backend
pip install -r requirements.txt
```

2. **配置 API Key**

复制 `.env.example` 为 `.env` 并填入 API Key:

```bash
cp .env.example .env
# 编辑 .env 文件，填入至少一个 LLM 的 API Key
```

3. **安装 VS Code 插件依赖**

```bash
cd extension
npm install
```

4. **编译插件**

```bash
npm run compile
```

5. **启动后端测试**

```bash
cd backend
python -m uvicorn app.main:app --reload
```

6. **配置前端后端地址（VS Code 设置）**

```json
{
  "tcAgent.backendUrl": "http://127.0.0.1:8765"
}
```

**启用 Runner 工具包（后端环境变量）**

```bash
export TC_AGENT_TOOL_PACKS=core,runner
```

**后端环境变量（推荐生产）**

```bash
# 工作区在后端的存储根目录
export TC_AGENT_WORKSPACE_ROOT=/data/tc_agent/workspaces
# OP-TEE 构建镜像
export TC_AGENT_OPTEE_IMAGE=tc-agent/optee-build:4.0
# 工作流存储（多实例建议使用 redis）
export TC_AGENT_WORKFLOW_STORE=redis   # memory | redis
export TC_AGENT_REDIS_URL=redis://localhost:6379/0
export TC_AGENT_WORKFLOW_TTL=86400
# Runner 后台模式（重任务异步化）
export TC_AGENT_RUNNER_BACKEND=redis   # inline | redis
export TC_AGENT_RUNNER_QUEUE_KEY=tc_agent:queue:runner
export TC_AGENT_RUNNER_POLL_INTERVAL=1.0
export TC_AGENT_RUNNER_TTL=86400
```

### Docker Compose 一键启动（后端 + Redis + Worker）

1. 复制后端环境文件并填写 API Key：

```bash
cp backend/.env.example backend/.env
```

2. 启动服务：

```bash
docker compose up -d --build
```

3. 后端默认端口：`http://127.0.0.1:8765`

> 注意：Runner 需要宿主机 Docker 权限，compose 已挂载 `/var/run/docker.sock`。

### 在 VS Code 中调试

1. 打开项目根目录
2. 按 F5 启动扩展开发宿主
3. 在新窗口中测试插件功能

## 配置说明

在 VS Code 设置中可配置以下选项:

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `tcAgent.backendUrl` | 后端服务地址 | `http://127.0.0.1:8000` |
| `tcAgent.llm.provider` | LLM 提供商 | `qwen` |
| `tcAgent.llm.qwenApiKey` | 通义千问 API Key | - |
| `tcAgent.llm.zhipuApiKey` | 智谱 API Key | - |
| `tcAgent.embedding.mode` | Embedding 模式 | `local` |

## 生产部署建议

- 多用户/多实例部署请启用 `TC_AGENT_WORKFLOW_STORE=redis` 以共享工作流状态
- Runner 需要后端服务器具备 Docker 与对应镜像
- 工作区文件由 VS Code 前端同步到后端工作区，再由 Runner 在容器中执行
- 如启用 `TC_AGENT_RUNNER_BACKEND=redis`，需单独启动 Runner Worker

## Runner Worker

启用 Redis Runner 后，使用独立进程处理编译/执行任务：

```bash
python -m app.worker.runner_worker
```
## 使用示例

### 示例任务: 生成 HELLO TA/CA 并运行 QEMU 验证

1. **Ask 模式**: 询问 "OP-TEE 中如何实现 AES-GCM?"
2. **Agent 模式**: 输入 "生成一个 HELLO TA/CA，并运行 QEMU 做验证"
3. **确认计划后自动执行**

生成的代码包括:
- TA 入口文件和头文件
- AES-GCM 实现代码
- CA 客户端代码
- Makefile 构建脚本

## 添加自定义知识（Ask 模式）

在 VS Code 中选中文件或右键文件，选择 `TC Agent: Add File to Knowledge Base`。
插件会读取本地文件内容并上传到后端知识库（不依赖服务器本地路径）。

## 开发路线

- [x] Phase 1: 基础框架
- [ ] Phase 2: RAG 系统集成
- [ ] Phase 3: LLM 多模型支持
- [ ] Phase 4: Agent 模式完善
- [ ] Phase 5: Docker 镜像拆分（build/runtime），降低体积并提升并发
- [ ] Phase 6: 完善与优化

### 生产上线 TODO
- [ ] 鉴权与多用户隔离（Workspace/Workflow 权限）
- [ ] 异步任务队列/Worker（Runner 长任务异步化）
- [ ] 资源限制与配额（并发、超时、磁盘）
- [ ] 监控与日志（请求、任务、异常追踪）
- [ ] 运行时安全（容器权限、镜像来源、命令白名单）
- [ ] CI / 回归测试

## 贡献指南

欢迎提交 Issue 和 Pull Request。

## License

MIT
