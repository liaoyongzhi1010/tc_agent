# TC Agent 设计文档

## 概述

TC Agent 是一个基于 VS Code 的可信计算开发助手插件，类似于 Copilot，专注于 OP-TEE/TrustZone 等可信计算领域的开发辅助。

## 设计决策

| 模块 | 决策 | 理由 |
|------|------|------|
| 架构 | TypeScript插件 + Python后端 | Python生态成熟，LangChain支持好 |
| 向量库 | Chroma | 轻量嵌入式，适合本地工具场景 |
| Embedding | 混合模式(本地+远程) | 兼顾离线可用和API效果 |
| RAG | Parent Document Retriever | 精确检索 + 充分上下文 |
| Agent | ReAct框架 | 思考-行动-观察闭环，可解释性好 |
| 通信 | REST + SSE/WebSocket | 普通请求用REST，流式用SSE/WS |
| 代码修改 | WorkspaceEdit API | VS Code原生支持，可undo |
| LLM | 支持Qwen/Zhipu/Doubao | 国内主流大模型 |

## 三种模式

### Ask模式
- 基于RAG的问答系统
- 知识库分为文本知识库和代码知识库
- 使用Parent Document Retriever实现small-to-big检索

### Plan模式
- 为用户任务生成结构化workflow
- 支持对话式迭代修改
- 确认后进入Code模式执行

### Code模式
- 基于LangChain ReAct框架
- 思考→行动→观察循环
- 工具分为通用工具和TEE专用工具
- 实时代码修改通过WorkspaceEdit API

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                VS Code Extension (TypeScript)                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────────┐  │
│  │  Ask    │  │  Plan   │  │  Code   │  │  Settings UI  │  │
│  │  View   │  │  View   │  │  View   │  │               │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └───────────────┘  │
│       └────────────┴────────────┴────┐                     │
│                Extension Core        │                     │
│  ┌───────────────────────────────────┴─────────────────┐   │
│  │  - Backend Process Manager                          │   │
│  │  - WorkspaceEdit Handler                            │   │
│  │  - SSE/WebSocket Client                             │   │
│  └─────────────────────┬───────────────────────────────┘   │
└────────────────────────┼───────────────────────────────────┘
                         │ HTTP/SSE/WebSocket
┌────────────────────────┼───────────────────────────────────┐
│                        ▼                                    │
│              Python Backend (FastAPI)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   API Layer                          │   │
│  │  /ask  /plan  /code  /knowledge  /config            │   │
│  └────────────────────┬────────────────────────────────┘   │
│  ┌────────────────────┴────────────────────────────────┐   │
│  │              Core Service Layer                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │ RAG      │  │ LLM      │  │ ReAct Agent      │   │   │
│  │  │ Service  │  │ Service  │  │ (Code Mode)      │   │   │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Infrastructure Layer                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │ Chroma   │  │ Embedding│  │ Tool Registry    │   │   │
│  │  │ Store    │  │ Manager  │  │                  │   │   │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
tc_agent/
├── extension/                    # VS Code插件
│   ├── src/
│   │   ├── extension.ts
│   │   ├── views/
│   │   ├── services/
│   │   └── config/
│   ├── package.json
│   └── tsconfig.json
│
├── backend/                      # Python后端
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   │   ├── rag/
│   │   │   ├── llm/
│   │   │   ├── embedding/
│   │   │   └── agent/
│   │   ├── tools/
│   │   │   ├── common/
│   │   │   └── tee/
│   │   ├── infrastructure/
│   │   └── schemas/
│   ├── knowledge/
│   ├── tests/
│   ├── pyproject.toml
│   └── requirements.txt
│
├── docs/
│   └── plans/
└── README.md
```

## TEE专用工具

1. **TA生成器** - 生成TA代码框架
2. **CA生成器** - 生成CA代码框架
3. **Crypto助手** - 生成加密操作代码(HMAC/AES/RSA)
4. **共享内存助手** - 生成共享内存操作代码
5. **安全验证器** - TA安全规范检查
6. **QEMU启动器** - 启动模拟环境
7. **xtest生成器** - 生成测试用例

## 实施路线

### Phase 1: 基础框架
- 搭建项目目录结构
- 实现Python后端基础框架
- 实现VS Code插件基础框架
- 实现后端进程管理
- 实现前后端通信

### Phase 2: RAG系统
- Chroma向量存储封装
- Parent Document Retriever
- Embedding管理器
- 预置知识库
- Ask模式完整流程

### Phase 3: LLM集成
- LLM抽象层
- 集成Qwen/Zhipu/Doubao
- 模型切换逻辑

### Phase 4: Plan模式
- Workflow数据模型
- 计划生成和修改
- Plan模式UI

### Phase 5: Code模式
- ReAct Agent核心
- 通用工具集
- TEE专用工具集
- WebSocket实时通信
- WorkspaceEdit集成

### Phase 6: 完善优化
- 日志系统
- 错误处理
- 性能优化
- 测试和文档
