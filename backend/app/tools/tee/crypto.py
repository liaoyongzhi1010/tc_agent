"""加密操作代码生成器"""
from typing import Dict, Any

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.crypto")


class CryptoHelper(BaseTool):
    """生成TEE内部加密操作代码"""

    name = "crypto_helper"
    description = "生成TEE内部加密操作代码(HMAC/AES/RSA等)"

    TEMPLATES = {
        "hmac_sha256": '''static TEE_Result do_hmac_sha256(const uint8_t *key, size_t key_len,
                                  const uint8_t *data, size_t data_len,
                                  uint8_t *mac, size_t *mac_len) {
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectHandle key_obj = TEE_HANDLE_NULL;
    TEE_Attribute attr;

    /* 分配操作句柄 */
    res = TEE_AllocateOperation(&op, TEE_ALG_HMAC_SHA256,
                                 TEE_MODE_MAC, key_len * 8);
    if (res != TEE_SUCCESS) goto cleanup;

    /* 创建密钥对象 */
    res = TEE_AllocateTransientObject(TEE_TYPE_HMAC_SHA256,
                                       key_len * 8, &key_obj);
    if (res != TEE_SUCCESS) goto cleanup;

    TEE_InitRefAttribute(&attr, TEE_ATTR_SECRET_VALUE, key, key_len);
    res = TEE_PopulateTransientObject(key_obj, &attr, 1);
    if (res != TEE_SUCCESS) goto cleanup;

    /* 设置密钥 */
    res = TEE_SetOperationKey(op, key_obj);
    if (res != TEE_SUCCESS) goto cleanup;

    /* 计算HMAC */
    TEE_MACInit(op, NULL, 0);
    TEE_MACUpdate(op, data, data_len);
    res = TEE_MACComputeFinal(op, NULL, 0, mac, mac_len);

cleanup:
    if (op != TEE_HANDLE_NULL) TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL) TEE_FreeTransientObject(key_obj);
    return res;
}''',
        "aes_gcm_encrypt": '''static TEE_Result do_aes_gcm_encrypt(const uint8_t *key, size_t key_len,
                                      const uint8_t *iv, size_t iv_len,
                                      const uint8_t *aad, size_t aad_len,
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

    res = TEE_AEInit(op, iv, iv_len, *tag_len * 8, aad_len, plain_len);
    if (res != TEE_SUCCESS) goto cleanup;

    if (aad_len > 0) {
        TEE_AEUpdateAAD(op, aad, aad_len);
    }

    res = TEE_AEEncryptFinal(op, plain, plain_len, cipher, cipher_len, tag, tag_len);

cleanup:
    if (op != TEE_HANDLE_NULL) TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL) TEE_FreeTransientObject(key_obj);
    return res;
}''',
        "rsa_sign": '''static TEE_Result do_rsa_sign(TEE_ObjectHandle key,
                               const uint8_t *digest, size_t digest_len,
                               uint8_t *sig, size_t *sig_len) {
    TEE_Result res;
    TEE_OperationHandle op = TEE_HANDLE_NULL;
    TEE_ObjectInfo key_info;

    TEE_GetObjectInfo1(key, &key_info);

    res = TEE_AllocateOperation(&op, TEE_ALG_RSASSA_PKCS1_V1_5_SHA256,
                                 TEE_MODE_SIGN, key_info.keySize);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_SetOperationKey(op, key);
    if (res != TEE_SUCCESS) goto cleanup;

    res = TEE_AsymmetricSignDigest(op, NULL, 0, digest, digest_len, sig, sig_len);

cleanup:
    if (op != TEE_HANDLE_NULL) TEE_FreeOperation(op);
    return res;
}''',
        "aes_gcm_decrypt": '''static TEE_Result do_aes_gcm_decrypt(const uint8_t *key, size_t key_len,
                                      const uint8_t *iv, size_t iv_len,
                                      const uint8_t *aad, size_t aad_len,
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

    res = TEE_AEInit(op, iv, iv_len, tag_len * 8, aad_len, cipher_len);
    if (res != TEE_SUCCESS) goto cleanup;

    if (aad_len > 0) {
        TEE_AEUpdateAAD(op, aad, aad_len);
    }

    res = TEE_AEDecryptFinal(op, cipher, cipher_len, plain, plain_len, tag, tag_len);

cleanup:
    if (op != TEE_HANDLE_NULL) TEE_FreeOperation(op);
    if (key_obj != TEE_HANDLE_NULL) TEE_FreeTransientObject(key_obj);
    return res;
}''',
    }

    async def execute(self, operation: str) -> ToolResult:
        if operation not in self.TEMPLATES:
            available = list(self.TEMPLATES.keys())
            return ToolResult(
                success=False, error=f"未知操作: {operation}, 可用: {available}"
            )

        logger.info("生成加密代码", operation=operation)

        return ToolResult(
            success=True, data={"code": self.TEMPLATES[operation], "operation": operation}
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "operation": {
                "type": "string",
                "enum": ["hmac_sha256", "aes_gcm_encrypt", "aes_gcm_decrypt", "rsa_sign"],
                "description": "加密操作类型: hmac_sha256(HMAC-SHA256), aes_gcm_encrypt(AES-GCM加密), aes_gcm_decrypt(AES-GCM解密), rsa_sign(RSA签名)",
            },
        }
