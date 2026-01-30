# 生产环境约束

## 运行环境
- secure 模式只建议在 Linux + /dev/kvm 运行
- simple 模式用于开发环境或 Mac

## 并发与资源
- 任务队列限流
- QEMU 容器设置 CPU/内存上限
- workspace 按任务隔离

## 镜像策略
- 预构建 + 版本化 + 私有仓库
- 生产环境禁止在线构建 Dockerfile
