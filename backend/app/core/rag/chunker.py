"""文档切分器"""
from abc import ABC, abstractmethod
from typing import List
import re


class BaseChunker(ABC):
    """切分器抽象基类"""

    @abstractmethod
    def chunk(self, text: str, chunk_size: int) -> List[str]:
        """将文本切分为多个chunk"""
        pass


class TextChunker(BaseChunker):
    """文本切分器,按段落和句子切分"""

    def __init__(self, overlap: int = 50):
        """
        Args:
            overlap: chunk之间的重叠字符数
        """
        self.overlap = overlap

    def chunk(self, text: str, chunk_size: int = 500) -> List[str]:
        """按段落和句子切分文本"""
        if not text or not text.strip():
            return []

        # 先按段落切分
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += ("\n\n" + para) if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落超过chunk_size,按句子切分
                if len(para) > chunk_size:
                    sentence_chunks = self._split_by_sentences(para, chunk_size)
                    chunks.extend(sentence_chunks[:-1])
                    current_chunk = sentence_chunks[-1] if sentence_chunks else ""
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_by_sentences(self, text: str, chunk_size: int) -> List[str]:
        """按句子切分"""
        # 中英文句子分隔符
        sentences = re.split(r"([。！？.!?])", text)

        chunks = []
        current_chunk = ""

        i = 0
        while i < len(sentences):
            sentence = sentences[i]
            # 把标点符号和前面的句子合并
            if i + 1 < len(sentences) and re.match(r"[。！？.!?]", sentences[i + 1]):
                sentence += sentences[i + 1]
                i += 1

            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

            i += 1

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


class CodeChunker(BaseChunker):
    """代码切分器,按函数/类切分"""

    # C语言函数模式
    C_FUNCTION_PATTERN = re.compile(
        r"(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{",
        re.MULTILINE,
    )

    # Python函数/类模式
    PYTHON_PATTERN = re.compile(
        r"^(def\s+\w+|class\s+\w+)", re.MULTILINE
    )

    def chunk(self, text: str, chunk_size: int = 1000) -> List[str]:
        """按函数/类切分代码"""
        if not text or not text.strip():
            return []

        # 检测语言类型
        if self._is_c_code(text):
            return self._chunk_c_code(text, chunk_size)
        elif self._is_python_code(text):
            return self._chunk_python_code(text, chunk_size)
        else:
            # 回退到通用行切分
            return self._chunk_by_lines(text, chunk_size)

    def _is_c_code(self, text: str) -> bool:
        """检测是否为C代码"""
        c_indicators = ["#include", "TEE_Result", "void ", "int ", "char "]
        return any(indicator in text for indicator in c_indicators)

    def _is_python_code(self, text: str) -> bool:
        """检测是否为Python代码"""
        py_indicators = ["def ", "class ", "import ", "from "]
        return any(indicator in text for indicator in py_indicators)

    def _chunk_c_code(self, text: str, chunk_size: int) -> List[str]:
        """切分C代码"""
        chunks = []
        lines = text.split("\n")

        current_chunk = []
        current_size = 0
        brace_count = 0
        in_function = False

        for line in lines:
            line_with_newline = line + "\n"
            current_chunk.append(line)
            current_size += len(line_with_newline)

            # 跟踪大括号
            brace_count += line.count("{") - line.count("}")

            # 检测函数开始
            if "{" in line and not in_function:
                in_function = True

            # 函数结束
            if in_function and brace_count == 0:
                in_function = False
                chunk_text = "\n".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text)
                current_chunk = []
                current_size = 0

            # 如果不在函数内且超过大小限制,切分
            elif not in_function and current_size >= chunk_size:
                chunk_text = "\n".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text)
                current_chunk = []
                current_size = 0

        # 处理剩余内容
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)

        return chunks

    def _chunk_python_code(self, text: str, chunk_size: int) -> List[str]:
        """切分Python代码"""
        chunks = []
        lines = text.split("\n")

        current_chunk = []
        current_size = 0

        for i, line in enumerate(lines):
            line_with_newline = line + "\n"

            # 检测新的函数/类定义(非嵌套)
            if re.match(r"^(def |class )", line) and current_chunk:
                # 保存当前chunk
                chunk_text = "\n".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text)
                current_chunk = []
                current_size = 0

            current_chunk.append(line)
            current_size += len(line_with_newline)

            # 超过大小限制且在空行处切分
            if current_size >= chunk_size and (not line.strip() or i == len(lines) - 1):
                chunk_text = "\n".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text)
                current_chunk = []
                current_size = 0

        # 处理剩余内容
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)

        return chunks

    def _chunk_by_lines(self, text: str, chunk_size: int) -> List[str]:
        """通用行切分"""
        chunks = []
        lines = text.split("\n")

        current_chunk = []
        current_size = 0

        for line in lines:
            line_with_newline = line + "\n"

            if current_size + len(line_with_newline) > chunk_size and current_chunk:
                chunk_text = "\n".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text)
                current_chunk = []
                current_size = 0

            current_chunk.append(line)
            current_size += len(line_with_newline)

        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)

        return chunks
