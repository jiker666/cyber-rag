"""OpenAI 兼容 Embedding API Provider(远程向量化服务)。"""
import logging

from app.core.config import get_settings
from app.core.errors import EmbeddingError
from app.embedding.base import BaseEmbedding

logger = logging.getLogger("cyber-rag.embedding.openai")


class OpenAICompatibleEmbedding(BaseEmbedding):
    """OpenAI 兼容 Embedding 接口, 通过环境变量配置, 密钥不落盘。"""

    name = "openai"

    def __init__(self):
        settings = get_settings()
        if not settings.embedding_api_key:
            raise EmbeddingError("EMBEDDING_PROVIDER=openai 时必须配置 EMBEDDING_API_KEY")
        self.model_name = settings.embedding_model
        self.dimension = settings.embedding_dimension
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI

            settings = get_settings()
            self._client = OpenAI(
                base_url=settings.embedding_api_base or None,
                api_key=settings.embedding_api_key,
                timeout=60,
            )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure_client()
        try:
            resp = self._client.embeddings.create(model=self.model_name, input=texts)
            return [item.embedding for item in resp.data]
        except Exception as e:
            logger.exception("远程 Embedding 调用失败")
            raise EmbeddingError(f"远程 Embedding 调用失败: {e}") from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]
