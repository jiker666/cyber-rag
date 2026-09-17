"""Embedding Provider 工厂: 根据环境变量构建单例。"""
import logging
import threading

from app.core.config import get_settings
from app.embedding.base import BaseEmbedding
from app.embedding.local_bge import LocalBGEEmbedding
from app.embedding.openai_compatible import OpenAICompatibleEmbedding

logger = logging.getLogger("cyber-rag.embedding.factory")

_provider: BaseEmbedding | None = None
_lock = threading.Lock()


def get_embedding_provider() -> BaseEmbedding:
    """获取全局 Embedding Provider 单例。"""
    global _provider
    if _provider is not None:
        return _provider
    with _lock:
        if _provider is not None:
            return _provider
        settings = get_settings()
        provider_type = settings.embedding_provider.lower()
        if provider_type == "openai":
            logger.info("使用远程 OpenAI 兼容 Embedding: %s", settings.embedding_model)
            _provider = OpenAICompatibleEmbedding()
        else:
            logger.info("使用本地 BGE Embedding: %s", settings.embedding_model)
            _provider = LocalBGEEmbedding()
        return _provider


def reset_embedding_provider() -> None:
    """测试用: 重置单例。"""
    global _provider
    with _lock:
        _provider = None
