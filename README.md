# TC Agent - 可信计算开发助手

基于 VS Code 的可信计算 (Trusted Computing) 开发助手插件，类似于 GitHub Copilot，专注于 OP-TEE/TrustZone 等可信计算领域的开发辅助。

## 功能特性

### 三种工作模式

1. **Ask 模式** - 基于 RAG 的智能问答
   - 支持纯文本知识库和代码知识库
   - 使用 Small-to-Big Retrieval 策略

2. **Plan 模式** - 任务规划
   - 为用户任务生成结构化 Workflow
   - 支持对话式迭代修改
   - 确认后进入 Code 模式执行

3. **Code 模式** - 代码生成与执行
   - 基于 LangChain ReAct 框架
   - 思考 → 行动 → 观察循环
   - 实时代码修改与反馈

### 可信计算专用工具

- TA/CA 代码框架生成器
- 加密操作代码生成 (HMAC/AES/RSA)
- 共享内存操作代码生成
- TA 安全规范检查器
- QEMU 模拟环境启动
- xtest 测试用例生成

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

**QEMU 验证配置（后端 .env）**

```dotenv
# simple: Mac 开发快速验证
# secure: 生产标准（QEMU 内执行 CA，CA_EXIT_CODE=0 才算成功）
TC_AGENT_QEMU_MODE=simple
# 可选：覆盖默认测试命令
TC_AGENT_QEMU_TEST_COMMAND=
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

### 在 VS Code 中调试

1. 打开项目根目录
2. 按 F5 启动扩展开发宿主
3. 在新窗口中测试插件功能

## 配置说明

在 VS Code 设置中可配置以下选项:

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `tcAgent.pythonPath` | Python 解释器路径 | `python3` |
| `tcAgent.backendPort` | 后端服务端口 | `8765` |
| `tcAgent.llm.provider` | LLM 提供商 | `qwen` |
| `tcAgent.llm.qwenApiKey` | 通义千问 API Key | - |
| `tcAgent.llm.zhipuApiKey` | 智谱 API Key | - |
| `tcAgent.embedding.mode` | Embedding 模式 | `local` |

## 使用示例

### 示例任务: 创建 HMAC 签名 TA

1. **Ask 模式**: 询问 "OP-TEE 中如何实现 HMAC 操作?"
2. **Plan 模式**: 输入 "创建一个 HMAC 签名的 TA，处理 4096bits 数据"
3. **确认计划后自动进入 Code 模式执行**

生成的代码包括:
- TA 入口文件和头文件
- HMAC-SHA256 实现代码
- CA 客户端代码
- Makefile 构建脚本

## 开发路线

- [x] Phase 1: 基础框架
- [ ] Phase 2: RAG 系统集成
- [ ] Phase 3: LLM 多模型支持
- [ ] Phase 4: Plan 模式完善
- [ ] Phase 5: Code 模式 (ReAct Agent)
- [ ] Phase 6: 完善与优化

## 贡献指南

欢迎提交 Issue 和 Pull Request。

## License

MIT
