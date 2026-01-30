# OP-TEE 加密操作 API

## 概述

OP-TEE 提供了符合 GlobalPlatform TEE Internal Core API 规范的加密操作接口。

## 操作句柄

加密操作使用操作句柄 (TEE_OperationHandle) 来管理状态。

### 分配操作

```c
TEE_Result TEE_AllocateOperation(TEE_OperationHandle *operation,
                                  uint32_t algorithm,
                                  uint32_t mode,
                                  uint32_t maxKeySize);
```

### 释放操作

```c
void TEE_FreeOperation(TEE_OperationHandle operation);
```

## 密钥管理

### 创建瞬态对象

```c
TEE_Result TEE_AllocateTransientObject(TEE_ObjectType objectType,
                                        uint32_t maxObjectSize,
                                        TEE_ObjectHandle *object);
```

### 设置属性

```c
void TEE_InitRefAttribute(TEE_Attribute *attr,
                          uint32_t attributeID,
                          const void *buffer,
                          size_t length);

TEE_Result TEE_PopulateTransientObject(TEE_ObjectHandle object,
                                        const TEE_Attribute *attrs,
                                        uint32_t attrCount);
```

### 绑定密钥

```c
TEE_Result TEE_SetOperationKey(TEE_OperationHandle operation,
                                TEE_ObjectHandle key);
```

## HMAC 操作

### 算法常量

- `TEE_ALG_HMAC_MD5`
- `TEE_ALG_HMAC_SHA1`
- `TEE_ALG_HMAC_SHA224`
- `TEE_ALG_HMAC_SHA256`
- `TEE_ALG_HMAC_SHA384`
- `TEE_ALG_HMAC_SHA512`

### 密钥类型

- `TEE_TYPE_HMAC_MD5`
- `TEE_TYPE_HMAC_SHA1`
- `TEE_TYPE_HMAC_SHA256`
- 等等

### 操作流程

```c
// 1. 分配操作
TEE_AllocateOperation(&op, TEE_ALG_HMAC_SHA256, TEE_MODE_MAC, 256);

// 2. 创建密钥对象
TEE_AllocateTransientObject(TEE_TYPE_HMAC_SHA256, 256, &key);
TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key_data, key_len);
TEE_PopulateTransientObject(key, &attr, 1);

// 3. 设置密钥
TEE_SetOperationKey(op, key);

// 4. 计算 HMAC
TEE_MACInit(op, NULL, 0);
TEE_MACUpdate(op, data, data_len);
TEE_MACComputeFinal(op, NULL, 0, mac, &mac_len);

// 5. 清理
TEE_FreeOperation(op);
TEE_FreeTransientObject(key);
```

## AES 操作

### 算法常量

- `TEE_ALG_AES_ECB_NOPAD`
- `TEE_ALG_AES_CBC_NOPAD`
- `TEE_ALG_AES_CTR`
- `TEE_ALG_AES_GCM`
- `TEE_ALG_AES_CCM`

### AES-GCM 加密

```c
// 1. 分配操作
TEE_AllocateOperation(&op, TEE_ALG_AES_GCM, TEE_MODE_ENCRYPT, 256);

// 2. 设置密钥
TEE_AllocateTransientObject(TEE_TYPE_AES, 256, &key);
TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key_data, 32);
TEE_PopulateTransientObject(key, &attr, 1);
TEE_SetOperationKey(op, key);

// 3. 初始化 AE
TEE_AEInit(op, iv, iv_len, tag_len * 8, aad_len, plain_len);

// 4. 处理 AAD
TEE_AEUpdateAAD(op, aad, aad_len);

// 5. 加密并生成 tag
TEE_AEEncryptFinal(op, plain, plain_len, cipher, &cipher_len, tag, &tag_len);
```

## RSA 操作

### 算法常量

- `TEE_ALG_RSASSA_PKCS1_V1_5_SHA256`
- `TEE_ALG_RSASSA_PKCS1_PSS_MGF1_SHA256`
- `TEE_ALG_RSAES_PKCS1_V1_5`
- `TEE_ALG_RSAES_PKCS1_OAEP_MGF1_SHA256`

### RSA 签名

```c
// 1. 分配操作
TEE_AllocateOperation(&op, TEE_ALG_RSASSA_PKCS1_V1_5_SHA256,
                      TEE_MODE_SIGN, key_size);

// 2. 设置密钥
TEE_SetOperationKey(op, rsa_key);

// 3. 签名
TEE_AsymmetricSignDigest(op, NULL, 0, digest, digest_len, sig, &sig_len);
```

## 错误处理

所有加密 API 都返回 `TEE_Result`，常见错误码：

- `TEE_SUCCESS`: 成功
- `TEE_ERROR_OUT_OF_MEMORY`: 内存不足
- `TEE_ERROR_BAD_PARAMETERS`: 参数错误
- `TEE_ERROR_SHORT_BUFFER`: 缓冲区太小
- `TEE_ERROR_MAC_INVALID`: MAC 验证失败
