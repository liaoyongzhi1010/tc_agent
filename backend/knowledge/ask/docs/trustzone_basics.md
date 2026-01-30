# TrustZone 基础

ARM TrustZone 将系统划分为安全世界 (Secure World) 与普通世界 (Normal World)。

## 关键概念
- Secure World：运行 TEE OS 和 TA
- Normal World：运行 Linux 和 CA
- SMC：世界切换调用
- TEE Client API：CA 调用 TA 的标准接口

## 对开发者的意义
- 把密钥与敏感逻辑放入 TA 中
- CA 只负责参数收集、业务流程、展示结果
- 所有可信计算任务应以“TA 安全执行 + CA 触发/验证”为核心
