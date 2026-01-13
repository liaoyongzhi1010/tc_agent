# OP-TEE 客户端应用(CA)开发指南

## 概述

CA (Client Application) 是运行在 REE (Rich Execution Environment) 中的应用程序，通过 TEE Client API 与 TA 通信。

## TEE Client API

### 头文件

```c
#include <tee_client_api.h>
```

### 初始化上下文

```c
TEEC_Result TEEC_InitializeContext(const char *name, TEEC_Context *context);
```

- `name`: 通常为 NULL，使用默认 TEE
- 返回 `TEEC_SUCCESS` 表示成功

### 清理上下文

```c
void TEEC_FinalizeContext(TEEC_Context *context);
```

### 打开会话

```c
TEEC_Result TEEC_OpenSession(TEEC_Context *context,
                              TEEC_Session *session,
                              const TEEC_UUID *destination,
                              uint32_t connectionMethod,
                              const void *connectionData,
                              TEEC_Operation *operation,
                              uint32_t *returnOrigin);
```

常用参数：
- `connectionMethod`: 通常使用 `TEEC_LOGIN_PUBLIC`
- `operation`: 可以为 NULL
- `returnOrigin`: 错误来源，可用于调试

### 关闭会话

```c
void TEEC_CloseSession(TEEC_Session *session);
```

### 调用命令

```c
TEEC_Result TEEC_InvokeCommand(TEEC_Session *session,
                                uint32_t commandID,
                                TEEC_Operation *operation,
                                uint32_t *returnOrigin);
```

## 参数传递

### TEEC_Operation

```c
typedef struct {
    uint32_t started;
    uint32_t paramTypes;
    TEEC_Parameter params[4];
    // ...
} TEEC_Operation;
```

### 参数类型

使用 `TEEC_PARAM_TYPES` 宏：

```c
op.paramTypes = TEEC_PARAM_TYPES(
    TEEC_MEMREF_TEMP_INPUT,
    TEEC_MEMREF_TEMP_OUTPUT,
    TEEC_NONE,
    TEEC_NONE
);
```

### 临时内存引用

```c
op.params[0].tmpref.buffer = input_buffer;
op.params[0].tmpref.size = input_size;
op.params[1].tmpref.buffer = output_buffer;
op.params[1].tmpref.size = output_size;
```

### 值参数

```c
op.params[0].value.a = value1;
op.params[0].value.b = value2;
```

## 共享内存

### 注册共享内存

```c
TEEC_SharedMemory shm;
shm.buffer = my_buffer;
shm.size = buffer_size;
shm.flags = TEEC_MEM_INPUT | TEEC_MEM_OUTPUT;

TEEC_Result res = TEEC_RegisterSharedMemory(context, &shm);
```

### 分配共享内存

```c
TEEC_SharedMemory shm;
shm.size = buffer_size;
shm.flags = TEEC_MEM_INPUT | TEEC_MEM_OUTPUT;

TEEC_Result res = TEEC_AllocateSharedMemory(context, &shm);
// 使用 shm.buffer
```

### 释放共享内存

```c
TEEC_ReleaseSharedMemory(&shm);
```

### 使用共享内存作为参数

```c
op.paramTypes = TEEC_PARAM_TYPES(
    TEEC_MEMREF_WHOLE,
    TEEC_NONE,
    TEEC_NONE,
    TEEC_NONE
);
op.params[0].memref.parent = &shm;
op.params[0].memref.size = shm.size;
op.params[0].memref.offset = 0;
```

## 完整示例

```c
#include <stdio.h>
#include <tee_client_api.h>
#include "my_ta.h"

int main() {
    TEEC_Context ctx;
    TEEC_Session sess;
    TEEC_Operation op;
    TEEC_UUID uuid = MY_TA_UUID;
    TEEC_Result res;
    uint32_t origin;

    // 初始化
    res = TEEC_InitializeContext(NULL, &ctx);
    if (res != TEEC_SUCCESS) {
        printf("InitializeContext failed: 0x%x\n", res);
        return 1;
    }

    // 打开会话
    res = TEEC_OpenSession(&ctx, &sess, &uuid,
                           TEEC_LOGIN_PUBLIC, NULL, NULL, &origin);
    if (res != TEEC_SUCCESS) {
        printf("OpenSession failed: 0x%x origin: 0x%x\n", res, origin);
        TEEC_FinalizeContext(&ctx);
        return 1;
    }

    // 准备参数
    char input[] = "Hello TA";
    char output[256] = {0};

    memset(&op, 0, sizeof(op));
    op.paramTypes = TEEC_PARAM_TYPES(
        TEEC_MEMREF_TEMP_INPUT,
        TEEC_MEMREF_TEMP_OUTPUT,
        TEEC_NONE,
        TEEC_NONE
    );
    op.params[0].tmpref.buffer = input;
    op.params[0].tmpref.size = strlen(input);
    op.params[1].tmpref.buffer = output;
    op.params[1].tmpref.size = sizeof(output);

    // 调用命令
    res = TEEC_InvokeCommand(&sess, CMD_PROCESS, &op, &origin);
    if (res == TEEC_SUCCESS) {
        printf("Output: %s\n", output);
    } else {
        printf("InvokeCommand failed: 0x%x origin: 0x%x\n", res, origin);
    }

    // 清理
    TEEC_CloseSession(&sess);
    TEEC_FinalizeContext(&ctx);

    return res == TEEC_SUCCESS ? 0 : 1;
}
```

## 编译

```makefile
CC = $(CROSS_COMPILE)gcc
CFLAGS = -Wall -I$(TEEC_EXPORT)/include
LDFLAGS = -L$(TEEC_EXPORT)/lib -lteec

my_ca: my_ca.c
    $(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)
```
