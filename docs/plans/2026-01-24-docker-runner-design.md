# Docker Runner 执行闭环设计

日期：2026-01-24

## 背景
当前系统已具备 TA/CA 代码生成、Docker 编译、QEMU 运行等工具，但流程分散，缺少“生成→执行→报错回传→修复→再次执行”的统一闭环。目标是新增一个 Runner 组件，将编译、运行、判定和日志统一收口，并满足生产级端到端验证要求。

## 目标
- 以单一工具完成：编译 TA/CA → QEMU 运行 → 成功判定 → 错误回传。
- 生产规范：**secure 模式必须跑 CA 端到端**；开发可用 simple 模式快速验证。
- 容器使用 `--rm`，执行结束自动销毁。
- 标准化输出，便于 LLM 迭代修复。

## 设计决策
- 选择 **方案 B（Runner 组件）**：新增 `workflow_runner`（或 `docker_runner`）工具，统一流程。
- 模式配置采用 **全局 `.env`**（后端启动读取）：`TC_AGENT_QEMU_MODE=simple|secure`。
- **secure 模式**为生产门禁：必须运行 CA 并成功；simple 模式不强制 CA 成功（避免误报失败）。

## 组件设计
### 1) 新增 Runner 工具
新增工具（示例名 `workflow_runner`），职责：
- 输入：`ta_dir`、`ca_dir`、`workspace_root`、`timeout`（可选）。
- 行为：
  1. 调用 `docker_build` 编译 TA。
  2. 调用 `docker_build` 编译 CA。
  3. 调用内部 QEMU 运行逻辑（或复用 `qemu_run`），传入 TA/CA。
  4. 解析输出、判断成功、返回结构化结果。

### 2) 运行模式与判定
- `.env` 配置：
  - `TC_AGENT_QEMU_MODE=simple|secure`
- 判定规则：
  - simple：编译成功 + QEMU 测试脚本完成即可。
  - secure：必须运行 CA 且 **CA_EXIT_CODE=0**。
- 成功标记：脚本输出中必须包含稳定标记（例如 `=== TEST_COMPLETE ===` 和 `CA_EXIT_CODE=0`）。

### 3) QEMU 脚本改造
在 `test_ta.sh` 与 `test_ta_simple.sh` 增加 CA 支持：
- 新增参数：`CA_FILE`（路径）。
- 在 rootfs 中将 CA 拷贝到 `/usr/bin` 并赋予可执行权限。
- 在 `rcS` 中执行 CA 并打印 `CA_EXIT_CODE=<code>`。
- 保留现有测试命令能力（用于扩展或调试）。

## 数据流
1. LLM 生成 TA/CA 代码。
2. Runner 编译 TA → 编译 CA。
3. Runner 根据 `TC_AGENT_QEMU_MODE` 选择脚本并运行 QEMU。
4. 解析输出，返回成功或错误细节。
5. 失败则 LLM 接收错误并修复，再进入下一轮执行。

## 错误处理与可观测性
- 统一输出结构：
  - `stage`: build_ta | build_ca | qemu_run
  - `returncode`
  - `stdout` / `stderr`
  - `hint`（可读修复建议）
- QEMU 输出必须包含稳定标记：
  - `=== TEST_START ===`
  - `=== TEST_COMPLETE ===`
  - `CA_EXIT_CODE=<code>`
- 所有 Runner 日志写入结构化 JSON（复用现有 logger）。

## 测试策略
- 本地：simple 模式快速验证（不作为生产门槛）。
- CI/生产：secure 模式强制 CA 端到端通过。
- Runner 解析逻辑可以用单元测试覆盖（模拟 stdout/stderr）。

## 风险与后续
- simple 模式无法完整覆盖 TrustZone 真实行为，因此仅用于开发加速。
- 若 QEMU 启动时间波动，需合理配置 timeout，并区分“超时失败”与“运行失败”。
- 后续可升级为队列/容器池化以提升吞吐，但当前不做。
