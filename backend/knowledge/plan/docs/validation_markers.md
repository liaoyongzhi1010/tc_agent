# QEMU 验证标记

稳定输出标记用于判定成功或失败：

- === TEST_COMPLETE ===
- CA_EXIT_CODE=<code>

## 规则
- simple 模式：出现 TEST_COMPLETE 即可
- secure 模式：必须 CA_EXIT_CODE=0

如果没有标记，视为运行失败或超时。
