# OP-TEE 概览

OP-TEE 是一个面向 ARM TrustZone 的开源 TEE (Trusted Execution Environment) 操作系统。它与普通世界 (REE/Linux) 并存，核心目标是把敏感逻辑放到安全世界中执行。

## 核心组件
- OP-TEE OS：安全世界内核运行环境
- OP-TEE Client：REE 侧用户态库 (libteec)
- TA (Trusted Application)：安全世界应用
- CA (Client Application)：REE 侧应用，调用 TA

## 开发最小闭环
1) TA/CA 代码生成
2) TA/CA 编译 (交叉编译)
3) QEMU 启动 OP-TEE
4) CA 调用 TA，验证结果

## 常见目录约定
- TA 头文件放在 `${TA_NAME}_ta/` 目录
- CA 的 Makefile 需要包含 `-I../${TA_NAME}_ta`

## 典型问题
- TA 未加载：`.ta` 文件未放入 `/lib/optee_armtz/`
- CA 调用失败：UUID 不一致或 TA 未编译成功
