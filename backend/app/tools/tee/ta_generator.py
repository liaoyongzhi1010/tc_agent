"""TA代码生成器"""
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

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

    HEADER_TEMPLATE = '''#ifndef _{name_upper}_TA_H
#define _{name_upper}_TA_H

#define {name_upper}_UUID \\
    {{ {uuid_formatted} }}

#define TA_CMD_PROCESS 0

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

    def _build_files(self, name: str, ta_uuid: str) -> Dict[str, str]:
        uuid_parts = ta_uuid.split("-")
        uuid_formatted = (
            f"0x{uuid_parts[0]}, 0x{uuid_parts[1]}, 0x{uuid_parts[2]}, \\\n"
            f"        {{ 0x{uuid_parts[3][:2]}, 0x{uuid_parts[3][2:]}, "
            f"0x{uuid_parts[4][:2]}, 0x{uuid_parts[4][2:4]}, "
            f"0x{uuid_parts[4][4:6]}, 0x{uuid_parts[4][6:8]}, "
            f"0x{uuid_parts[4][8:10]}, 0x{uuid_parts[4][10:]} }}"
        )

        return {
            f"{name}_ta.c": self.TA_TEMPLATE.format(name=name, uuid=ta_uuid),
            f"{name}_ta.h": self.HEADER_TEMPLATE.format(
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
        overwrite: bool = True,
        emit_files: bool = False,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            if cancel_event and cancel_event.is_set():
                return ToolResult(success=False, error="已取消")

            ta_uuid = ta_uuid or str(uuid.uuid4())
            output_path = Path(output_dir) / f"{name}_ta"
            files = self._build_files(name=name, ta_uuid=ta_uuid)

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
                        "uuid": ta_uuid,
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
            "overwrite": {
                "type": "boolean",
                "description": "是否覆盖已存在目录(默认true)",
            },
            "emit_files": {
                "type": "boolean",
                "description": "仅返回文件内容，不落盘(默认false)",
            },
        }
