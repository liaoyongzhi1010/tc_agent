# OP-TEE 可信应用(TA)开发指南

## 概述

OP-TEE (Open Portable Trusted Execution Environment) 是一个开源的 TEE 实现，遵循 GlobalPlatform TEE 规范。TA (Trusted Application) 是运行在 TEE 中的安全应用程序。

## TA 基本结构

一个 TA 需要实现以下入口函数：

### TA_CreateEntryPoint
TA 加载时调用，用于初始化全局资源。

```c
TEE_Result TA_CreateEntryPoint(void) {
    return TEE_SUCCESS;
}
```

### TA_DestroyEntryPoint
TA 卸载时调用，用于清理全局资源。

```c
void TA_DestroyEntryPoint(void) {
}
```

### TA_OpenSessionEntryPoint
客户端打开会话时调用。

```c
TEE_Result TA_OpenSessionEntryPoint(uint32_t param_types,
                                     TEE_Param params[4],
                                     void **sess_ctx) {
    return TEE_SUCCESS;
}
```

### TA_CloseSessionEntryPoint
客户端关闭会话时调用。

```c
void TA_CloseSessionEntryPoint(void *sess_ctx) {
}
```

### TA_InvokeCommandEntryPoint
客户端调用命令时调用，是 TA 的主要业务逻辑入口。

```c
TEE_Result TA_InvokeCommandEntryPoint(void *sess_ctx,
                                       uint32_t cmd_id,
                                       uint32_t param_types,
                                       TEE_Param params[4]) {
    switch (cmd_id) {
    case CMD_DO_SOMETHING:
        return do_something(param_types, params);
    default:
        return TEE_ERROR_BAD_PARAMETERS;
    }
}
```

## 参数类型

TEE_Param 有四种类型：

- `TEE_PARAM_TYPE_NONE`: 无参数
- `TEE_PARAM_TYPE_VALUE_INPUT`: 输入值
- `TEE_PARAM_TYPE_VALUE_OUTPUT`: 输出值
- `TEE_PARAM_TYPE_VALUE_INOUT`: 输入输出值
- `TEE_PARAM_TYPE_MEMREF_INPUT`: 输入内存引用
- `TEE_PARAM_TYPE_MEMREF_OUTPUT`: 输出内存引用
- `TEE_PARAM_TYPE_MEMREF_INOUT`: 输入输出内存引用

使用 `TEE_PARAM_TYPES` 宏定义参数类型组合：

```c
uint32_t exp_types = TEE_PARAM_TYPES(
    TEE_PARAM_TYPE_MEMREF_INPUT,
    TEE_PARAM_TYPE_MEMREF_OUTPUT,
    TEE_PARAM_TYPE_NONE,
    TEE_PARAM_TYPE_NONE
);

if (param_types != exp_types)
    return TEE_ERROR_BAD_PARAMETERS;
```

## UUID

每个 TA 需要唯一的 UUID，在头文件中定义：

```c
#define MY_TA_UUID \
    { 0x12345678, 0x1234, 0x1234, \
      { 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0 } }
```

## 编译

TA 使用 OP-TEE 的 TA 开发套件编译：

```makefile
BINARY = <uuid>
include $(TA_DEV_KIT_DIR)/mk/ta_dev_kit.mk
```

## 签名

编译后的 TA 需要签名才能在 TEE 中加载。开发环境使用默认测试密钥，生产环境需要使用安全的私钥签名。
