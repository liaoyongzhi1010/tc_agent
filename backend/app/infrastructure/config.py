"""TC Agent 配置管理"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """应用配置,支持环境变量和.env文件"""

    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = False

    # 数据目录 (默认在代码目录下的 data 文件夹)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")

    # LLM配置
    llm_provider: str = "qwen"  # qwen, zhipu, doubao
    llm_model: Optional[str] = None

    # API Keys
    qwen_api_key: Optional[str] = None
    zhipu_api_key: Optional[str] = None
    doubao_api_key: Optional[str] = None
    doubao_endpoint_id: Optional[str] = None

    # Embedding配置
    embedding_mode: str = "local"  # local, remote
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_api_key: Optional[str] = None

    # RAG配置
    rag_child_chunk_size: int = 200
    rag_parent_chunk_size: int = 1000
    rag_top_k: int = 5

    # QEMU配置
    qemu_mode: str = "simple"  # simple, secure
    qemu_test_command: Optional[str] = None

    # Agent配置
    agent_max_iterations: int = 30

    class Config:
        env_file = ".env"
        env_prefix = "TC_AGENT_"

    def get_llm_api_key(self) -> str:
        """获取当前LLM提供商的API Key"""
        keys = {
            "qwen": self.qwen_api_key,
            "zhipu": self.zhipu_api_key,
            "doubao": self.doubao_api_key,
        }
        return keys.get(self.llm_provider, "") or ""

    def get_default_model(self) -> str:
        """获取默认模型"""
        if self.llm_model:
            return self.llm_model

        defaults = {
            "qwen": "qwen-turbo",
            "zhipu": "glm-4-flash",
            "doubao": self.doubao_endpoint_id or "",
        }
        return defaults.get(self.llm_provider, "")


# 全局配置实例
settings = Settings()

# 确保数据目录存在
settings.data_dir.mkdir(parents=True, exist_ok=True)
