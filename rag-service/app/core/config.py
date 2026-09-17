"""全局配置: 通过环境变量注入, 敏感信息不落盘。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# rag-service 目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[BASE_DIR / ".env", BASE_DIR.parent / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务
    app_name: str = "cyber-rag-service"
    rag_service_port: int = 8000
    log_level: str = "INFO"
    # Java 后端与 RAG 服务之间的内部通信令牌, 为空则不校验
    rag_internal_token: str = ""

    # LLM (OpenAI Compatible)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # LLM 协议: openai(OpenAI 兼容 /chat/completions) | anthropic(Anthropic 兼容 /v1/messages)
    llm_provider: str = "openai"
    llm_timeout: int = 120
    llm_max_tokens: int = 2048

    # Embedding
    embedding_provider: str = "local"  # local / openai
    embedding_model: str = "BAAI/bge-m3"
    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_dimension: int = 1024
    embedding_device: str = ""  # 自动选择; 可指定 cpu/cuda/mps
    embedding_batch_size: int = 16

    # Reranker
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_max_length: int = 512

    # 向量数据库
    chroma_persist_dir: str = str(BASE_DIR / "data" / "chroma")

    # 默认 RAG 参数
    default_chunk_size: int = 512
    default_chunk_overlap: int = 100
    default_top_k: int = 5
    default_temperature: float = 0.3
    default_score_threshold: float = 0.3
    default_history_window: int = 6

    # 上传
    upload_dir: str = str(BASE_DIR / "data" / "uploads")
    max_file_size_mb: int = 20

    @property
    def model_dir(self) -> str:
        return str(BASE_DIR / "models_cache")


@lru_cache
def get_settings() -> Settings:
    return Settings()
