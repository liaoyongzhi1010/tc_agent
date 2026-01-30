# workflow_runner 执行规范

## 输入
- ta_dir: TA 目录路径
- ca_dir: CA 目录路径 (secure 模式必填)
- timeout: 超时时间

## 执行顺序
1) docker_build 编译 TA
2) docker_build 编译 CA
3) qemu_run 运行测试

## 判定规则
- 必须包含 TEST_COMPLETE
- secure 模式必须包含 CA_EXIT_CODE=0

## 输出
- stage: build_ta / build_ca / qemu_run / complete
- stdout / stderr / returncode
- error_type (编译/链接/运行/超时)
