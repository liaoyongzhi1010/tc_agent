# 常见错误分类

## build_ta / build_ca
- compile_error: 语法错误、缺少头文件、Makefile 目标错误
- link_error: undefined reference、ld 失败
- timeout: 编译超时

## qemu_run
- run_error: QEMU 启动失败、TA 未加载、CA 运行错误
- timeout: QEMU 测试超时

## 处置建议
- compile_error: 检查 include 路径、Makefile 变量
- link_error: 检查库路径、链接顺序
- run_error: 确认 TA 已生成并放入 /lib/optee_armtz/
