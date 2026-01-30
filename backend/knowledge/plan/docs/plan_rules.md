# Plan 生成规则 (Agent)

## 目标
生成可执行的工作流，确保后续 Agent 步骤必须调用工具完成任务。

## 必须遵循
- 单任务只允许一个项目目录
- 先 ta_generator、再 ca_generator、最后 workflow_runner
- secure 模式必须有 CA 且 CA_EXIT_CODE=0
- 所有路径必须在 workspace_root 内

## 推荐输出
- Step 1: 生成 TA/CA 模板
- Step 2: 编译并运行验证 (workflow_runner)
