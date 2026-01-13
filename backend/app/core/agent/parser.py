"""Agent输出解析器"""
import re
import json
from typing import Union, Optional
from dataclasses import dataclass

from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.agent.parser")


@dataclass
class ThinkResult:
    """思考结果"""
    content: str


@dataclass
class Action:
    """行动"""
    tool: str
    input: dict


@dataclass
class FinalAnswer:
    """最终答案"""
    content: str


class AgentOutputParser:
    """解析Agent输出"""

    def parse(self, output: str) -> Union[ThinkResult, Action, FinalAnswer]:
        """解析LLM输出"""
        output = output.strip()

        # 检查是否是最终答案
        final_match = re.search(
            r"最终答案[：:]\s*(.+)", output, re.DOTALL | re.IGNORECASE
        )
        if final_match:
            return FinalAnswer(content=final_match.group(1).strip())

        # 检查是否有行动
        action_match = re.search(
            r"行动[：:]\s*(\S+)", output, re.IGNORECASE
        )
        if action_match:
            tool_name = action_match.group(1).strip()

            # 提取输入参数
            input_match = re.search(
                r"输入[：:]\s*(.+?)(?=\n(?:思考|行动|观察|最终)|$)",
                output,
                re.DOTALL | re.IGNORECASE,
            )

            tool_input = {}
            if input_match:
                input_str = input_match.group(1).strip()
                # 尝试解析JSON
                try:
                    # 清理可能的markdown代码块
                    input_str = re.sub(r"```json?\s*", "", input_str)
                    input_str = re.sub(r"```", "", input_str)
                    tool_input = json.loads(input_str)
                except json.JSONDecodeError:
                    # 如果不是JSON，作为单个参数处理
                    tool_input = {"input": input_str}

            # 提取思考内容
            think_match = re.search(
                r"思考[：:]\s*(.+?)(?=\n行动|$)", output, re.DOTALL | re.IGNORECASE
            )
            thought = think_match.group(1).strip() if think_match else ""

            return Action(tool=tool_name, input=tool_input)

        # 只有思考
        think_match = re.search(
            r"思考[：:]\s*(.+)", output, re.DOTALL | re.IGNORECASE
        )
        if think_match:
            return ThinkResult(content=think_match.group(1).strip())

        # 无法解析，作为思考返回
        return ThinkResult(content=output)

    def extract_thought(self, output: str) -> Optional[str]:
        """提取思考内容"""
        match = re.search(
            r"思考[：:]\s*(.+?)(?=\n(?:行动|最终)|$)",
            output,
            re.DOTALL | re.IGNORECASE,
        )
        return match.group(1).strip() if match else None
