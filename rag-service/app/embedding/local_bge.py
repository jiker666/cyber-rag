"""本地 BGE Embedding: 基于 sentence-transformers 加载 BAAI 系列模型。"""
import logging
from functools import lru_cache

from app.core.config import get_settings
from app.core.errors import EmbeddingError
from app.embedding.base import BaseEmbedding

logger = logging.getLogger("cyber-rag.embedding.local")


class LocalBGEEmbedding(BaseEmbedding):
    """本地 BGE Embedding(默认 BAAI/bge-m3, 中文与中英技术文本表现优秀)。"""

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self._batch_size = settings.embedding_batch_size
        self._model = None  # 懒加载: 首次调用时加载模型

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:  # pragma: no cover
                raise EmbeddingError("sentence-transformers 未安装") from e
            settings = get_settings()
            device = settings.embedding_device or None
            logger.info("加载本地 Embedding 模型 %s (device=%s)", self.model_name, device or "auto")
            self._model = SentenceTransformer(
                self.model_name, device=device, cache_folder=settings.model_dir
            )
            self.dimension = self._model.get_sentence_embedding_dimension()
            logger.info("Embedding 模型加载完成, dimension=%s", self.dimension)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        try:
            embeddings = self._model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,  # BGE 要求归一化后使用余弦/内积
                show_progress_bar=False,
            )
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.exception("文档向量化失败")
            raise EmbeddingError(f"文档向量化失败: {e}") from e

    def embed_query(self, text: str) -> list[float]:
        self._ensure_model()
        try:
            embedding = self._model.encode(
                [text], normalize_embeddings=True, show_progress_bar=False
            )[0]
            return embedding.tolist()
        except Exception as e:
            logger.exception("查询向量化失败")
            raise EmbeddingError(f"查询向量化失败: {e}") from e
