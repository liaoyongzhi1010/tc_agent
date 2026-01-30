/*
 * aesgcm - Trusted Application (AES-GCM Simple)
 * UUID: a908c83b-8b50-4f5d-8d62-709be5261d7b
 */

#include <tee_internal_api.h>
#include <tee_internal_api_extensions.h>
#include "aesgcm_ta.h"

#define TAG_LEN 16

static TEE_Result do_aes_gcm_encrypt(const uint8_t *key, size_t key_len,
                                     const uint8_t *iv, size_t iv_len,
                                     const uint8_t *plain, size_t plain_len,
                                     uint8_t *cipher, size_t *cipher_len,
                                     uint8_t *tag, size_t *tag_len);
static TEE_Result do_aes_gcm_decrypt(const uint8_t *key, size_t key_len,
                                     const uint8_t *iv, size_t iv_len,
                                     const uint8_t *cipher, size_t cipher_len,
                                     uint8_t *plain, size_t *plain_len,
                                     const uint8_t *tag, size_t tag_len);

static TEE_Result cmd_encrypt(uint32_t param_types, TEE_Param params[4]);
static TEE_Result cmd_decrypt(uint32_t param_types, TEE_Param params[4]);

TEE_Result TA_CreateEntryPoint(void) {
    DMSG("TA_CreateEntryPoint");
    return TEE_SUCCESS;
}

void TA_DestroyEntryPoint(void) {
    DMSG("TA_DestroyEntryPoint");
}

TEE_Result TA_OpenSessionEntryPoint(uint32_t param_types,
                                     TEE_Param params[4],
                                     void **sess_ctx) {
    (void)param_types;
    (void)params;
    (void)sess_ctx;
    DMSG("TA_OpenSessionEntryPoint");
    return TEE_SUCCESS;
}

void TA_CloseSessionEntryPoint(void *sess_ctx) {
    (void)sess_ctx;
    DMSG("TA_CloseSessionEntryPoint");
}

TEE_Result TA_InvokeCommandEntryPoint(void *sess_ctx,
                                       uint32_t cmd_id,
                                       uint32_t param_types,
                                       TEE_Param params[4]) {
    (void)sess_ctx;

    switch (cmd_id) {
    case TA_CMD_AES_GCM_ENCRYPT:
        return cmd_encrypt(param_types, params);
    case TA_CMD_AES_GCM_DECRYPT:
        return cmd_decrypt(param_types, params);
    default:
        return TEE_ERROR_BAD_PARAMETERS;
    }
}

static TEE_Result cmd_encrypt(uint32_t param_types, TEE_Param params[4]) {
    const uint32_t exp = TEE_PARAM_TYPES(
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_OUTPUT
    );

    if (param_types != exp) {
        EMSG("Bad param_types: 0x%x", param_types);
        return TEE_ERROR_BAD_PARAMETERS;
    }

    const uint8_t *key = params[0].memref.buffer;
    size_t key_len = params[0].memref.size;
    const uint8_t *iv = params[1].memref.buffer;
    size_t iv_len = params[1].memref.size;
    const uint8_t *plain = params[2].memref.buffer;
    size_t plain_len = params[2].memref.size;
    uint8_t *out = params[3].memref.buffer;
    size_t out_len = params[3].memref.size;

    if (out_len < plain_len + TAG_LEN) {
        EMSG("Output buffer too small");
        params[3].memref.size = plain_len + TAG_LEN;
        return TEE_ERROR_SHORT_BUFFER;
    }

    size_t cipher_len = plain_len;
    uint8_t tag[TAG_LEN] = {0};
    size_t tag_len = TAG_LEN;

    TEE_Result res = do_aes_gcm_encrypt(
        key, key_len, iv, iv_len,
        plain, plain_len,
        out, &cipher_len,
        tag, &tag_len
    );
    if (res != TEE_SUCCESS) {
        EMSG("Encrypt failed: 0x%x", res);
        return res;
    }

    TEE_MemMove(out + cipher_len, tag, tag_len);
    params[3].memref.size = cipher_len + tag_len;
    return TEE_SUCCESS;
}

static TEE_Result cmd_decrypt(uint32_t param_types, TEE_Param params[4]) {
    const uint32_t exp = TEE_PARAM_TYPES(
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_OUTPUT
    );

    if (param_types != exp) {
        EMSG("Bad param_types: 0x%x", param_types);
        return TEE_ERROR_BAD_PARAMETERS;
    }

    const uint8_t *key = params[0].memref.buffer;
    size_t key_len = params[0].memref.size;
    const uint8_t *iv = params[1].memref.buffer;
    size_t iv_len = params[1].memref.size;
    const uint8_t *in = params[2].memref.buffer;
    size_t in_len = params[2].memref.size;
    uint8_t *out = params[3].memref.buffer;
    size_t out_len = params[3].memref.size;

    if (in_len <= TAG_LEN) {
        EMSG("Input too short");
        return TEE_ERROR_BAD_PARAMETERS;
    }

    size_t cipher_len = in_len - TAG_LEN;
    const uint8_t *tag = in + cipher_len;

    if (out_len < cipher_len) {
        EMSG("Output buffer too small");
        params[3].memref.size = cipher_len;
        return TEE_ERROR_SHORT_BUFFER;
    }

    TEE_Result res = do_aes_gcm_decrypt(
        key, key_len, iv, iv_len,
        in, cipher_len,
        out, &out_len,
        tag, TAG_LEN
    );
    if (res != TEE_SUCCESS) {
        EMSG("Decrypt failed: 0x%x", res);
        return res;
    }

    params[3].memref.size = out_len;
    return TEE_SUCCESS;
}

static TEE_Result do_aes_gcm_encrypt(const uint8_t *key, size_t key_len,
                                     const uint8_t *iv, size_t iv_len,
                                     const uint8_t *plain, size_t plain_len,
                                     uint8_t *cipher, size_t *cipher_len,
                                     uint8_t *tag, size_t *tag_len) {
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectHandle key_obj = TEE_HANDLE_NULL;
    TEE_Attribute attr;

    res = TEE_AllocateOperation(&op, TEE_ALG_AES_GCM,
                                 TEE_MODE_ENCRYPT, key_len * 8);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AllocateTransientObject(TEE_TYPE_AES, key_len * 8, &key_obj);
    if (res != TEE_SUCCESS) goto cleanup;

    TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_len);
    res = TEE_PopulateTransientObject(key_obj, &attr, 1);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_SetOperationKey(op, key_obj);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AEInit(op, iv, iv_len, *tag_len * 8, 0, plain_len);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AEEncryptFinal(op, plain, plain_len, cipher, cipher_len, tag, tag_len);

cleanup:
    if (op != TEE_HANDLE_NULL) TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL) TEE_FreeTransientObject(key_obj);
    return res;
}

static TEE_Result do_aes_gcm_decrypt(const uint8_t *key, size_t key_len,
                                     const uint8_t *iv, size_t iv_len,
                                     const uint8_t *cipher, size_t cipher_len,
                                     uint8_t *plain, size_t *plain_len,
                                     const uint8_t *tag, size_t tag_len) {
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectHandle key_obj = TEE_HANDLE_NULL;
    TEE_Attribute attr;

    res = TEE_AllocateOperation(&op, TEE_ALG_AES_GCM,
                                 TEE_MODE_DECRYPT, key_len * 8);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AllocateTransientObject(TEE_TYPE_AES, key_len * 8, &key_obj);
    if (res != TEE_SUCCESS) goto cleanup;

    TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_len);
    res = TEE_PopulateTransientObject(key_obj, &attr, 1);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_SetOperationKey(op, key_obj);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AEInit(op, iv, iv_len, tag_len * 8, 0, cipher_len);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AEDecryptFinal(op, cipher, cipher_len, plain, plain_len, tag, tag_len);

cleanup:
    if (op != TEE_HANDLE_NULL) TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL) TEE_FreeTransientObject(key_obj);
    return res;
}
