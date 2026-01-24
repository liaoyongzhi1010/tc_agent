"""TA代码生成器"""
import uuid
from pathlib import Path
from typing import Dict, Any

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.ta_generator")


class TAGenerator(BaseTool):
    """生成OP-TEE TA(Trusted Application)代码框架"""

    name = "ta_generator"
    description = "生成OP-TEE TA(Trusted Application)代码框架,包括入口文件、头文件和Makefile"

    TA_TEMPLATE = '''/*
 * {name} - Trusted Application
 * UUID: {uuid}
 */

#include <tee_internal_api.h>
#include <tee_internal_api_extensions.h>
#include "{name}_ta.h"

/* Forward declarations */
static TEE_Result process_command(uint32_t param_types, TEE_Param params[4]);

TEE_Result TA_CreateEntryPoint(void) {{
    DMSG("TA_CreateEntryPoint");
    return TEE_SUCCESS;
}}

void TA_DestroyEntryPoint(void) {{
    DMSG("TA_DestroyEntryPoint");
}}

TEE_Result TA_OpenSessionEntryPoint(uint32_t param_types,
                                     TEE_Param params[4],
                                     void **sess_ctx) {{
    (void)param_types;
    (void)params;
    (void)sess_ctx;
    DMSG("TA_OpenSessionEntryPoint");
    return TEE_SUCCESS;
}}

void TA_CloseSessionEntryPoint(void *sess_ctx) {{
    (void)sess_ctx;
    DMSG("TA_CloseSessionEntryPoint");
}}

TEE_Result TA_InvokeCommandEntryPoint(void *sess_ctx,
                                       uint32_t cmd_id,
                                       uint32_t param_types,
                                       TEE_Param params[4]) {{
    (void)sess_ctx;

    switch (cmd_id) {{
    case TA_CMD_PROCESS:
        return process_command(param_types, params);
    default:
        return TEE_ERROR_BAD_PARAMETERS;
    }}
}}

static TEE_Result process_command(uint32_t param_types, TEE_Param params[4]) {{
    /* TODO: 实现业务逻辑 */
    (void)param_types;
    (void)params;
    return TEE_SUCCESS;
}}
'''

    AES_GCM_TA_TEMPLATE = '''/*
 * {name} - Trusted Application (AES-GCM Simple)
 * UUID: {uuid}
 */

#include <tee_internal_api.h>
#include <tee_internal_api_extensions.h>
#include "{name}_ta.h"

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

TEE_Result TA_CreateEntryPoint(void) {{
    DMSG("TA_CreateEntryPoint");
    return TEE_SUCCESS;
}}

void TA_DestroyEntryPoint(void) {{
    DMSG("TA_DestroyEntryPoint");
}}

TEE_Result TA_OpenSessionEntryPoint(uint32_t param_types,
                                     TEE_Param params[4],
                                     void **sess_ctx) {{
    (void)param_types;
    (void)params;
    (void)sess_ctx;
    DMSG("TA_OpenSessionEntryPoint");
    return TEE_SUCCESS;
}}

void TA_CloseSessionEntryPoint(void *sess_ctx) {{
    (void)sess_ctx;
    DMSG("TA_CloseSessionEntryPoint");
}}

TEE_Result TA_InvokeCommandEntryPoint(void *sess_ctx,
                                       uint32_t cmd_id,
                                       uint32_t param_types,
                                       TEE_Param params[4]) {{
    (void)sess_ctx;

    switch (cmd_id) {{
    case TA_CMD_AES_GCM_ENCRYPT:
        return cmd_encrypt(param_types, params);
    case TA_CMD_AES_GCM_DECRYPT:
        return cmd_decrypt(param_types, params);
    default:
        return TEE_ERROR_BAD_PARAMETERS;
    }}
}}

static TEE_Result cmd_encrypt(uint32_t param_types, TEE_Param params[4]) {{
    const uint32_t exp = TEE_PARAM_TYPES(
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_OUTPUT
    );

    if (param_types != exp) {{
        EMSG("Bad param_types: 0x%x", param_types);
        return TEE_ERROR_BAD_PARAMETERS;
    }}

    const uint8_t *key = params[0].memref.buffer;
    size_t key_len = params[0].memref.size;
    const uint8_t *iv = params[1].memref.buffer;
    size_t iv_len = params[1].memref.size;
    const uint8_t *plain = params[2].memref.buffer;
    size_t plain_len = params[2].memref.size;
    uint8_t *out = params[3].memref.buffer;
    size_t out_len = params[3].memref.size;

    if (out_len < plain_len + TAG_LEN) {{
        EMSG("Output buffer too small");
        params[3].memref.size = plain_len + TAG_LEN;
        return TEE_ERROR_SHORT_BUFFER;
    }}

    size_t cipher_len = plain_len;
    uint8_t tag[TAG_LEN] = {{0}};
    size_t tag_len = TAG_LEN;

    TEE_Result res = do_aes_gcm_encrypt(
        key, key_len, iv, iv_len,
        plain, plain_len,
        out, &cipher_len,
        tag, &tag_len
    );
    if (res != TEE_SUCCESS) {{
        EMSG("Encrypt failed: 0x%x", res);
        return res;
    }}

    TEE_MemMove(out + cipher_len, tag, tag_len);
    params[3].memref.size = cipher_len + tag_len;
    return TEE_SUCCESS;
}}

static TEE_Result cmd_decrypt(uint32_t param_types, TEE_Param params[4]) {{
    const uint32_t exp = TEE_PARAM_TYPES(
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_INPUT,
        TEE_PARAM_TYPE_MEMREF_OUTPUT
    );

    if (param_types != exp) {{
        EMSG("Bad param_types: 0x%x", param_types);
        return TEE_ERROR_BAD_PARAMETERS;
    }}

    const uint8_t *key = params[0].memref.buffer;
    size_t key_len = params[0].memref.size;
    const uint8_t *iv = params[1].memref.buffer;
    size_t iv_len = params[1].memref.size;
    const uint8_t *in = params[2].memref.buffer;
    size_t in_len = params[2].memref.size;
    uint8_t *out = params[3].memref.buffer;
    size_t out_len = params[3].memref.size;

    if (in_len <= TAG_LEN) {{
        EMSG("Input too short");
        return TEE_ERROR_BAD_PARAMETERS;
    }}

    size_t cipher_len = in_len - TAG_LEN;
    const uint8_t *tag = in + cipher_len;

    if (out_len < cipher_len) {{
        EMSG("Output buffer too small");
        params[3].memref.size = cipher_len;
        return TEE_ERROR_SHORT_BUFFER;
    }}

    TEE_Result res = do_aes_gcm_decrypt(
        key, key_len, iv, iv_len,
        in, cipher_len,
        out, &out_len,
        tag, TAG_LEN
    );
    if (res != TEE_SUCCESS) {{
        EMSG("Decrypt failed: 0x%x", res);
        return res;
    }}

    params[3].memref.size = out_len;
    return TEE_SUCCESS;
}}

static TEE_Result do_aes_gcm_encrypt(const uint8_t *key, size_t key_len,
                                     const uint8_t *iv, size_t iv_len,
                                     const uint8_t *plain, size_t plain_len,
                                     uint8_t *cipher, size_t *cipher_len,
                                     uint8_t *tag, size_t *tag_len) {{
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
}}

static TEE_Result do_aes_gcm_decrypt(const uint8_t *key, size_t key_len,
                                     const uint8_t *iv, size_t iv_len,
                                     const uint8_t *cipher, size_t cipher_len,
                                     uint8_t *plain, size_t *plain_len,
                                     const uint8_t *tag, size_t tag_len) {{
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
}}
'''

    HEADER_TEMPLATE = '''#ifndef _{name_upper}_TA_H
#define _{name_upper}_TA_H

#define {name_upper}_UUID \\
    {{ {uuid_formatted} }}

#define TA_CMD_PROCESS 0

#endif /* _{name_upper}_TA_H */
'''

    AES_GCM_HEADER_TEMPLATE = '''#ifndef _{name_upper}_TA_H
#define _{name_upper}_TA_H

#define {name_upper}_UUID \\
    {{ {uuid_formatted} }}

#define TA_CMD_AES_GCM_ENCRYPT 1
#define TA_CMD_AES_GCM_DECRYPT 2

#endif /* _{name_upper}_TA_H */
'''

    MAKEFILE_TEMPLATE = '''BINARY = {uuid}

include $(TA_DEV_KIT_DIR)/mk/ta_dev_kit.mk
'''

    SUB_MK_TEMPLATE = '''srcs-y += {name}_ta.c
'''

    USER_TA_HEADER_DEFINES_TEMPLATE = '''#ifndef USER_TA_HEADER_DEFINES_H
#define USER_TA_HEADER_DEFINES_H

#include "{name}_ta.h"

#define TA_UUID {name_upper}_UUID

#define TA_FLAGS                    (TA_FLAG_EXEC_DDR | TA_FLAG_SINGLE_INSTANCE)
#define TA_STACK_SIZE               (2 * 1024)
#define TA_DATA_SIZE                (32 * 1024)

#define TA_CURRENT_TA_EXT_PROPERTIES \\
    {{ "gp.ta.description", USER_TA_PROP_TYPE_STRING, "{name} TA" }}, \\
    {{ "gp.ta.version", USER_TA_PROP_TYPE_U32, &(const uint32_t){{ 0x0010 }} }}

#endif /* USER_TA_HEADER_DEFINES_H */
'''

    def _build_files(self, name: str, ta_uuid: str, template: str = None) -> Dict[str, str]:
        uuid_parts = ta_uuid.split("-")
        uuid_formatted = (
            f"0x{uuid_parts[0]}, 0x{uuid_parts[1]}, 0x{uuid_parts[2]}, \\\n"
            f"        {{ 0x{uuid_parts[3][:2]}, 0x{uuid_parts[3][2:]}, "
            f"0x{uuid_parts[4][:2]}, 0x{uuid_parts[4][2:4]}, "
            f"0x{uuid_parts[4][4:6]}, 0x{uuid_parts[4][6:8]}, "
            f"0x{uuid_parts[4][8:10]}, 0x{uuid_parts[4][10:]} }}"
        )

        if template == "aes_gcm_simple":
            ta_template = self.AES_GCM_TA_TEMPLATE
            header_template = self.AES_GCM_HEADER_TEMPLATE
        else:
            ta_template = self.TA_TEMPLATE
            header_template = self.HEADER_TEMPLATE

        return {
            f"{name}_ta.c": ta_template.format(name=name, uuid=ta_uuid),
            f"{name}_ta.h": header_template.format(
                name_upper=name.upper(), uuid_formatted=uuid_formatted
            ),
            "Makefile": self.MAKEFILE_TEMPLATE.format(uuid=ta_uuid),
            "sub.mk": self.SUB_MK_TEMPLATE.format(name=name),
            "user_ta_header_defines.h": self.USER_TA_HEADER_DEFINES_TEMPLATE.format(
                name=name, name_upper=name.upper()
            ),
        }

    async def execute(
        self,
        name: str,
        output_dir: str,
        ta_uuid: str = None,
        template: str = None,
    ) -> ToolResult:
        try:
            ta_uuid = ta_uuid or str(uuid.uuid4())
            output_path = Path(output_dir) / f"{name}_ta"
            output_path.mkdir(parents=True, exist_ok=True)
            files = self._build_files(name=name, ta_uuid=ta_uuid, template=template)

            created_files = []
            for filename, content in files.items():
                filepath = output_path / filename
                filepath.write_text(content)
                created_files.append(str(filepath))

            logger.info("TA生成完成", name=name, uuid=ta_uuid, path=str(output_path))

            return ToolResult(
                success=True,
                data={
                    "uuid": ta_uuid,
                    "output_dir": str(output_path),
                    "files": created_files,
                },
            )
        except Exception as e:
            logger.error("TA生成失败", name=name, error=str(e))
            return ToolResult(success=False, error=str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": {"type": "string", "description": "TA名称"},
            "output_dir": {"type": "string", "description": "输出目录"},
            "ta_uuid": {"type": "string", "description": "TA UUID(可选,自动生成)"},
            "template": {
                "type": "string",
                "enum": ["aes_gcm_simple"],
                "description": "可选模板：aes_gcm_simple",
            },
        }
