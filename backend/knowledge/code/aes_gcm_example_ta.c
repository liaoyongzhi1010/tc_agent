/*
 * AES-GCM 加密示例 TA
 * 演示如何在 OP-TEE 中实现 AES-GCM 加密操作
 */

#include <tee_internal_api.h>
#include <tee_internal_api_extensions.h>
#include <string.h>

#define TA_AES_CMD_ENCRYPT 0
#define TA_AES_CMD_DECRYPT 1

#define AES_KEY_SIZE 32  /* 256 bits */
#define GCM_IV_SIZE  12
#define GCM_TAG_SIZE 16

/* AES-GCM 加密 */
static TEE_Result do_aes_gcm_encrypt(
    const uint8_t *key, size_t key_len,
    const uint8_t *iv, size_t iv_len,
    const uint8_t *aad, size_t aad_len,
    const uint8_t *plain, size_t plain_len,
    uint8_t *cipher, size_t *cipher_len,
    uint8_t *tag, size_t *tag_len)
{
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectHandle key_obj = TEE_HANDLE_NULL;
    TEE_Attribute attr;

    /* 分配 AES-GCM 操作 */
    res = TEE_AllocateOperation(&op, TEE_ALG_AES_GCM,
                                 TEE_MODE_ENCRYPT, key_len * 8);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AllocateOperation failed: 0x%x", res);
        goto cleanup;
    }

    /* 创建密钥对象 */
    res = TEE_AllocateTransientObject(TEE_TYPE_AES, key_len * 8, &key_obj);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AllocateTransientObject failed: 0x%x", res);
        goto cleanup;
    }

    /* 设置密钥 */
    TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_len);
    res = TEE_PopulateTransientObject(key_obj, &attr, 1);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_PopulateTransientObject failed: 0x%x", res);
        goto cleanup;
    }

    res = TEE_SetOperationKey(op, key_obj);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_SetOperationKey failed: 0x%x", res);
        goto cleanup;
    }

    /* 初始化 AE 操作 */
    res = TEE_AEInit(op, iv, iv_len, *tag_len * 8, aad_len, plain_len);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AEInit failed: 0x%x", res);
        goto cleanup;
    }

    /* 处理 AAD */
    if (aad_len > 0) {
        TEE_AEUpdateAAD(op, aad, aad_len);
    }

    /* 加密并生成 tag */
    res = TEE_AEEncryptFinal(op, plain, plain_len,
                              cipher, cipher_len, tag, tag_len);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AEEncryptFinal failed: 0x%x", res);
    }

cleanup:
    if (op != TEE_HANDLE_NULL)
        TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL)
        TEE_FreeTransientObject(key_obj);

    return res;
}

/* AES-GCM 解密 */
static TEE_Result do_aes_gcm_decrypt(
    const uint8_t *key, size_t key_len,
    const uint8_t *iv, size_t iv_len,
    const uint8_t *aad, size_t aad_len,
    const uint8_t *cipher, size_t cipher_len,
    const uint8_t *tag, size_t tag_len,
    uint8_t *plain, size_t *plain_len)
{
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectHandle key_obj = TEE_HANDLE_NULL;
    TEE_Attribute attr;

    /* 分配操作 */
    res = TEE_AllocateOperation(&op, TEE_ALG_AES_GCM,
                                 TEE_MODE_DECRYPT, key_len * 8);
    if (res != TEE_SUCCESS)
        goto cleanup;

    /* 创建并设置密钥 */
    res = TEE_AllocateTransientObject(TEE_TYPE_AES, key_len * 8, &key_obj);
    if (res != TEE_SUCCESS)
        goto cleanup;

    TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_len);
    res = TEE_PopulateTransientObject(key_obj, &attr, 1);
    if (res != TEE_SUCCESS)
        goto cleanup;

    res = TEE_SetOperationKey(op, key_obj);
    if (res != TEE_SUCCESS)
        goto cleanup;

    /* 初始化 */
    res = TEE_AEInit(op, iv, iv_len, tag_len * 8, aad_len, cipher_len);
    if (res != TEE_SUCCESS)
        goto cleanup;

    /* 处理 AAD */
    if (aad_len > 0) {
        TEE_AEUpdateAAD(op, aad, aad_len);
    }

    /* 解密并验证 tag */
    res = TEE_AEDecryptFinal(op, cipher, cipher_len,
                              plain, plain_len, tag, tag_len);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AEDecryptFinal failed: 0x%x (MAC invalid?)", res);
    }

cleanup:
    if (op != TEE_HANDLE_NULL)
        TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL)
        TEE_FreeTransientObject(key_obj);

    return res;
}

TEE_Result TA_CreateEntryPoint(void)
{
    return TEE_SUCCESS;
}

void TA_DestroyEntryPoint(void)
{
}

TEE_Result TA_OpenSessionEntryPoint(uint32_t param_types,
                                     TEE_Param params[4],
                                     void **sess_ctx)
{
    (void)param_types;
    (void)params;
    (void)sess_ctx;
    return TEE_SUCCESS;
}

void TA_CloseSessionEntryPoint(void *sess_ctx)
{
    (void)sess_ctx;
}

TEE_Result TA_InvokeCommandEntryPoint(void *sess_ctx,
                                       uint32_t cmd_id,
                                       uint32_t param_types,
                                       TEE_Param params[4])
{
    (void)sess_ctx;
    (void)param_types;
    (void)params;

    /* 简化示例,实际使用需要验证参数类型 */
    switch (cmd_id) {
    case TA_AES_CMD_ENCRYPT:
        /* 实现加密逻辑 */
        return TEE_SUCCESS;
    case TA_AES_CMD_DECRYPT:
        /* 实现解密逻辑 */
        return TEE_SUCCESS;
    default:
        return TEE_ERROR_BAD_PARAMETERS;
    }
}
