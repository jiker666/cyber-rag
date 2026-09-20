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
    # 检索策略: vector(纯向量) | hybrid(向量 + BM25 RRF 融合)
    retrieval_strategy: str = "vector"
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

    # ---- Security-Aware Adaptive RAG ----
    # 自适应总开关(请求级 adaptive 参数可覆盖)
    adaptive_enabled: bool = False
    # 精确实体强匹配加权(EXACT 路由下命中 CVE/CWE 等编号的 RRF 确定性加分)
    entity_boost_enabled: bool = True
    # Confidences-aware Reranker Gating 阈值
    rerank_confidence_threshold: float = 0.75  # top1 相似度高于此 → 高置信
    rerank_score_margin_threshold: float = 0.08  # top1-top2 分差高于此 → 排序稳定
    rerank_agreement_threshold: float = 0.6  # vector/BM25 Top-5 重合率高于此 → 双路一致
    complexity_threshold: float = 7.5  # 复杂度(0-10)达到此值才允许多跳分解
    # FAST 路由(简单事实题向量直出)判定阈值
    fast_path_top1_min: float = 0.72
    fast_path_margin_min: float = 0.10
    # Dynamic Context Budget
    max_context_tokens: int = 3000  # 送入 LLM 的上下文 Token 预算(估算口径)
    min_context_chunks: int = 2
    max_context_chunks: int = 6
    # Cache
    embedding_cache_size: int = 512
    retrieval_cache_size: int = 256
    # 启动预热(避免首问 5s/后续 1s 的答辩体验问题)
    warmup_enabled: bool = True
    # Small-to-Large(parent-child)分块参数
    parent_chunk_size: int = 1024
    child_chunk_size: int = 320
    child_chunk_overlap: int = 60

    # 上传
    upload_dir: str = str(BASE_DIR / "data" / "uploads")
    max_file_size_mb: int = 20

    @property
    def model_dir(self) -> str:
        return str(BASE_DIR / "models_cache")


@lru_cache
def get_settings() -> Settings:
    return Settings()
