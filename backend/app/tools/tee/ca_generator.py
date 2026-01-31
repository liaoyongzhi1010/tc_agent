"""CA代码生成器"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.ca_generator")


class CAGenerator(BaseTool):
    """生成OP-TEE CA(Client Application)代码框架"""

    name = "ca_generator"
    description = "生成OP-TEE CA(Client Application)代码框架,与指定TA通信"

    CA_TEMPLATE = '''/*
 * {name} - Client Application
 * 与TA {ta_name} 通信
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tee_client_api.h>
#include "{ta_name}_ta.h"

struct tee_ctx {{
    TEEC_Context ctx;
    TEEC_Session sess;
}};

static TEEC_Result init_tee_session(struct tee_ctx *ctx) {{
    TEEC_UUID uuid = {ta_name_upper}_UUID;
    TEEC_Result res;
    uint32_t err_origin;

    res = TEEC_InitializeContext(NULL, &ctx->ctx);
    if (res != TEEC_SUCCESS) {{
        fprintf(stderr, "TEEC_InitializeContext failed: 0x%x\\n", res);
        return res;
    }}

    res = TEEC_OpenSession(&ctx->ctx, &ctx->sess, &uuid,
                           TEEC_LOGIN_PUBLIC, NULL, NULL, &err_origin);
    if (res != TEEC_SUCCESS) {{
        fprintf(stderr, "TEEC_OpenSession failed: 0x%x origin: 0x%x\\n",
                res, err_origin);
        TEEC_FinalizeContext(&ctx->ctx);
        return res;
    }}

    return TEEC_SUCCESS;
}}

static void cleanup_tee_session(struct tee_ctx *ctx) {{
    TEEC_CloseSession(&ctx->sess);
    TEEC_FinalizeContext(&ctx->ctx);
}}

static TEEC_Result invoke_ta_command(struct tee_ctx *ctx,
                                      const uint8_t *input, size_t input_len,
                                      uint8_t *output, size_t *output_len) {{
    TEEC_Operation op;
    TEEC_Result res;
    uint32_t err_origin;

    memset(&op, 0, sizeof(op));
    op.paramTypes = TEEC_PARAM_TYPES(
        TEEC_MEMREF_TEMP_INPUT,
        TEEC_MEMREF_TEMP_OUTPUT,
        TEEC_NONE,
        TEEC_NONE
    );

    op.params[0].tmpref.buffer = (void *)input;
    op.params[0].tmpref.size = input_len;
    op.params[1].tmpref.buffer = output;
    op.params[1].tmpref.size = *output_len;

    res = TEEC_InvokeCommand(&ctx->sess, TA_CMD_PROCESS, &op, &err_origin);
    if (res != TEEC_SUCCESS) {{
        fprintf(stderr, "TEEC_InvokeCommand failed: 0x%x origin: 0x%x\\n",
                res, err_origin);
        return res;
    }}

    *output_len = op.params[1].tmpref.size;
    return TEEC_SUCCESS;
}}

int main(int argc, char *argv[]) {{
    struct tee_ctx ctx;
    TEEC_Result res;

    /* 初始化示例数据 */
    const char *input_data = "Hello from CA";
    uint8_t output[256];
    size_t output_len = sizeof(output);

    printf("{name} - Starting\\n");

    /* 初始化TEE会话 */
    res = init_tee_session(&ctx);
    if (res != TEEC_SUCCESS) {{
        return 1;
    }}

    /* 调用TA */
    res = invoke_ta_command(&ctx, (uint8_t *)input_data, strlen(input_data),
                            output, &output_len);
    if (res == TEEC_SUCCESS) {{
        printf("TA returned %zu bytes\\n", output_len);
    }}

    /* 清理 */
    cleanup_tee_session(&ctx);

    return res == TEEC_SUCCESS ? 0 : 1;
}}
'''

    MAKEFILE_TEMPLATE = '''CC = $(CROSS_COMPILE)gcc
CFLAGS = -Wall -I$(TEEC_EXPORT)/include -I../{ta_name}_ta
LDFLAGS = -L$(TEEC_EXPORT)/lib -lteec

BINARY = {name}

.PHONY: all clean

all: $(BINARY)

$(BINARY): {name}.c
\t$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
\trm -f $(BINARY)
'''

    def _build_files(self, name: str, ta_name: str) -> Dict[str, str]:
        ca_template = self.CA_TEMPLATE
        return {
            f"{name}.c": ca_template.format(
                name=name, ta_name=ta_name, ta_name_upper=ta_name.upper()
            ),
            "Makefile": self.MAKEFILE_TEMPLATE.format(name=name, ta_name=ta_name),
        }

    async def execute(
        self,
        name: str,
        ta_name: str,
        output_dir: str,
        overwrite: bool = True,
        emit_files: bool = False,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            if cancel_event and cancel_event.is_set():
                return ToolResult(success=False, error="已取消")

            output_path = Path(output_dir) / f"{name}_ca"

            files = self._build_files(name=name, ta_name=ta_name)

            if emit_files:
                file_ops = []
                created_files = []
                for filename, content in files.items():
                    filepath = output_path / filename
                    file_ops.append(
                        {
                            "path": str(filepath),
                            "content": content,
                            "encoding": "utf-8",
                            "create_dirs": True,
                        }
                    )
                    created_files.append(str(filepath))

                return ToolResult(
                    success=True,
                    data={
                        "output_dir": str(output_path),
                        "files": created_files,
                        "file_ops": file_ops,
                    },
                )

            if output_path.exists() and not overwrite:
                return ToolResult(success=False, error=f"输出目录已存在: {output_path}")
            existed_before = output_path.exists()
            output_path.mkdir(parents=True, exist_ok=True)

            created_files = []
            for filename, content in files.items():
                filepath = output_path / filename
                filepath.write_text(content)
                created_files.append(str(filepath))

            logger.info("CA生成完成", name=name, ta_name=ta_name, path=str(output_path))

            return ToolResult(
                success=True,
                data={
                    "output_dir": str(output_path),
                    "files": created_files,
                },
            )
        except Exception as e:
            logger.error("CA生成失败", name=name, error=str(e))
            return ToolResult(success=False, error=str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": {"type": "string", "description": "CA名称"},
            "ta_name": {"type": "string", "description": "对应的TA名称"},
            "output_dir": {"type": "string", "description": "输出目录"},
            "overwrite": {
                "type": "boolean",
                "description": "是否覆盖已存在目录(默认true)",
            },
            "emit_files": {
                "type": "boolean",
                "description": "仅返回文件内容，不落盘(默认false)",
            },
        }
