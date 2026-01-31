# optee_runner 执行规范

## 输入
- workspace_id: 后端工作区 ID（必须）
- ta_dir: TA 目录（相对工作区，必须）
- ca_dir: CA 目录（相对工作区，可选）
- ca_bin: CA 可执行文件（相对工作区，可选）
- mode: build / test / full
- timeout: 超时时间（秒）

## 执行顺序
1) build: 编译 TA + CA（如提供 ca_dir）
2) full: build + QEMU 运行验证
3) test: 仅运行测试（需 ca_dir / ca_bin）

## 判定规则
- build 成功则返回 exit_code=0
- full/test 需要检测运行日志，确保执行完成

## 输出
- success / error
- log（截断后的 stdout）
- exit_code

## 示例
```
行动: optee_runner
输入: {"workspace_id": "<id>", "ta_dir": "demo_ta", "ca_dir": "demo_ca", "mode": "build", "timeout": 180}
```
