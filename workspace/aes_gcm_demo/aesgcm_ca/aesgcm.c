/*
 * aesgcm - Client Application (AES-GCM Simple)
 * 与TA aesgcm 通信
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tee_client_api.h>
#include "aesgcm_ta.h"

#define TAG_LEN 16

struct tee_ctx {
    TEEC_Context ctx;
    TEEC_Session sess;
};

static TEEC_Result init_tee_session(struct tee_ctx *ctx) {
    TEEC_UUID uuid = AESGCM_UUID;
    TEEC_Result res;
    uint32_t err_origin;

    res = TEEC_InitializeContext(NULL, &ctx->ctx);
    if (res != TEEC_SUCCESS) {
        fprintf(stderr, "TEEC_InitializeContext failed: 0x%x\n", res);
        return res;
    }

    res = TEEC_OpenSession(&ctx->ctx, &ctx->sess, &uuid,
                           TEEC_LOGIN_PUBLIC, NULL, NULL, &err_origin);
    if (res != TEEC_SUCCESS) {
        fprintf(stderr, "TEEC_OpenSession failed: 0x%x origin: 0x%x\n",
                res, err_origin);
        TEEC_FinalizeContext(&ctx->ctx);
        return res;
    }

    return TEEC_SUCCESS;
}

static void cleanup_tee_session(struct tee_ctx *ctx) {
    TEEC_CloseSession(&ctx->sess);
    TEEC_FinalizeContext(&ctx->ctx);
}

static TEEC_Result invoke_aes_cmd(struct tee_ctx *ctx,
                                  uint32_t cmd_id,
                                  const uint8_t *key, size_t key_len,
                                  const uint8_t *iv, size_t iv_len,
                                  const uint8_t *input, size_t input_len,
                                  uint8_t *output, size_t *output_len) {
    TEEC_Operation op;
    TEEC_Result res;
    uint32_t err_origin;

    memset(&op, 0, sizeof(op));
    op.paramTypes = TEEC_PARAM_TYPES(
        TEEC_MEMREF_TEMP_INPUT,
        TEEC_MEMREF_TEMP_INPUT,
        TEEC_MEMREF_TEMP_INPUT,
        TEEC_MEMREF_TEMP_OUTPUT
    );

    op.params[0].tmpref.buffer = (void *)key;
    op.params[0].tmpref.size = key_len;
    op.params[1].tmpref.buffer = (void *)iv;
    op.params[1].tmpref.size = iv_len;
    op.params[2].tmpref.buffer = (void *)input;
    op.params[2].tmpref.size = input_len;
    op.params[3].tmpref.buffer = output;
    op.params[3].tmpref.size = *output_len;

    res = TEEC_InvokeCommand(&ctx->sess, cmd_id, &op, &err_origin);
    if (res != TEEC_SUCCESS) {
        fprintf(stderr, "TEEC_InvokeCommand failed: 0x%x origin: 0x%x\n",
                res, err_origin);
        return res;
    }

    *output_len = op.params[3].tmpref.size;
    return TEEC_SUCCESS;
}

int main(int argc, char *argv[]) {
    struct tee_ctx ctx;
    TEEC_Result res;

    const uint8_t key[16] = {
        0x00, 0x01, 0x02, 0x03,
        0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b,
        0x0c, 0x0d, 0x0e, 0x0f
    };
    const uint8_t iv[12] = {
        0xa0, 0xa1, 0xa2, 0xa3,
        0xa4, 0xa5, 0xa6, 0xa7,
        0xa8, 0xa9, 0xaa, 0xab
    };
    const uint8_t plain[] = "Hello AES-GCM";

    uint8_t cipher[sizeof(plain) + TAG_LEN] = {0};
    size_t cipher_len = sizeof(cipher);
    uint8_t plain_out[sizeof(plain)] = {0};
    size_t plain_out_len = sizeof(plain_out);

    printf("aesgcm - Starting AES-GCM simple test\n");

    res = init_tee_session(&ctx);
    if (res != TEEC_SUCCESS) {
        return 1;
    }

    res = invoke_aes_cmd(&ctx, TA_CMD_AES_GCM_ENCRYPT,
                         key, sizeof(key), iv, sizeof(iv),
                         plain, sizeof(plain) - 1,
                         cipher, &cipher_len);
    if (res != TEEC_SUCCESS) {
        cleanup_tee_session(&ctx);
        return 1;
    }

    res = invoke_aes_cmd(&ctx, TA_CMD_AES_GCM_DECRYPT,
                         key, sizeof(key), iv, sizeof(iv),
                         cipher, cipher_len,
                         plain_out, &plain_out_len);
    if (res != TEEC_SUCCESS) {
        cleanup_tee_session(&ctx);
        return 1;
    }

    if (plain_out_len != sizeof(plain) - 1 ||
        memcmp(plain_out, plain, sizeof(plain) - 1) != 0) {
        fprintf(stderr, "Decrypt verify failed\n");
        cleanup_tee_session(&ctx);
        return 1;
    }

    printf("AES-GCM test passed\n");
    cleanup_tee_session(&ctx);
    return 0;
}
