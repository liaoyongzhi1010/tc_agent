# OP-TEE 开发流程

## 最小开发步骤
1) 生成 TA 模板
2) 生成 CA 模板
3) 在 TA 中实现业务逻辑
4) 在 CA 中调用 TA 并处理结果
5) 编译 TA/CA
6) 在 QEMU 中运行验证

## 常见编译参数
- TA 编译需要 TA_DEV_KIT_DIR
- CA 编译需要 TEEC_EXPORT

## 常见运行验证
- secure 模式下要求 CA 退出码为 0
- QEMU 输出需要稳定标记：TEST_COMPLETE / CA_EXIT_CODE
