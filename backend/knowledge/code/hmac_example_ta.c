/*
 * HMAC-SHA256 示例 TA
 * 演示如何在 OP-TEE 中实现 HMAC 操作
 */

#include <tee_internal_api.h>
#include <tee_internal_api_extensions.h>
#include <string.h>

#define TA_HMAC_CMD_COMPUTE 0

/* 计算 HMAC-SHA256 */
static TEE_Result do_hmac_sha256(const uint8_t *key, size_t key_len,
                                  const uint8_t *data, size_t data_len,
                                  uint8_t *mac, size_t *mac_len)
{
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectHandle key_obj = TEE_HANDLE_NULL;
    TEE_Attribute attr;

    /* 检查输出缓冲区大小 */
    if (*mac_len < 32) {
        EMSG("Output buffer too small");
        return TEE_ERROR_SHORT_BUFFER;
    }

    /* 分配 HMAC 操作 */
    res = TEE_AllocateOperation(&op, TEE_ALG_HMAC_SHA256,
                                 TEE_MODE_MAC, key_len * 8);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AllocateOperation failed: 0x%x", res);
        goto cleanup;
    }

    /* 创建密钥对象 */
    res = TEE_AllocateTransientObject(TEE_TYPE_HMAC_SHA256,
                                       key_len * 8, &key_obj);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_AllocateTransientObject failed: 0x%x", res);
        goto cleanup;
    }

    /* 设置密钥属性 */
    TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_len);
    res = TEE_PopulateTransientObject(key_obj, &attr, 1);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_PopulateTransientObject failed: 0x%x", res);
        goto cleanup;
    }

    /* 绑定密钥到操作 */
    res = TEE_SetOperationKey(op, key_obj);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_SetOperationKey failed: 0x%x", res);
        goto cleanup;
    }

    /* 执行 HMAC 计算 */
    TEE_MACInit(op, NULL, 0);
    TEE_MACUpdate(op, data, data_len);
    res = TEE_MACComputeFinal(op, NULL, 0, mac, mac_len);
    if (res != TEE_SUCCESS) {
        EMSG("TEE_MACComputeFinal failed: 0x%x", res);
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
    DMSG("HMAC TA created");
    return TEE_SUCCESS;
}

void TA_DestroyEntryPoint(void)
{
    DMSG("HMAC TA destroyed");
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

    /* 验证参数类型 */
    uint32_t exp_types = TEE_PARAM_TYPES(
        TEE_PARAM_TYPE_MEMREF_INPUT,   /* 密钥 */
        TEE_PARAM_TYPE_MEMREF_INPUT,   /* 数据 */
        TEE_PARAM_TYPE_MEMREF_OUTPUT,  /* HMAC 输出 */
        TEE_PARAM_TYPE_NONE
    );

    if (param_types != exp_types) {
        EMSG("Bad parameter types");
        return TEE_ERROR_BAD_PARAMETERS;
    }

    switch (cmd_id) {
    case TA_HMAC_CMD_COMPUTE:
        return do_hmac_sha256(
            params[0].memref.buffer, params[0].memref.size,
            params[1].memref.buffer, params[1].memref.size,
            params[2].memref.buffer, &params[2].memref.size
        );
    default:
        return TEE_ERROR_BAD_PARAMETERS;
    }
}
