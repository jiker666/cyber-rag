"""Embedding 层抽象: 上层只依赖该接口, 可无缝切换本地 BGE 或远程 API。"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("cyber-rag.embedding")


class BaseEmbedding(ABC):
    """Embedding Provider 统一接口。"""

    name: str = "base"
    dimension: int = 0

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """对文档 Chunk 批量向量化(用于入库)。"""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """对用户查询向量化(用于检索)。"""

    def info(self) -> dict:
        return {"provider": self.name, "model": getattr(self, "model_name", ""), "dimension": self.dimension}
