"""Reranker: 可选的 CrossEncoder 重排序(BAAI/bge-reranker-base), 懒加载。"""
import logging
import threading

from app.core.config import get_settings

logger = logging.getLogger("cyber-rag.rag.reranker")


class BaseReranker:
    """重排序器接口。"""

    name = "base"

    def rerank(self, query: str, chunks: list, top_n: int = 3) -> list:
        """对 chunks 重排序并截断至 top_n, 返回的元素带 rerank_score 字段。"""
        raise NotImplementedError


class CrossEncoderReranker(BaseReranker):
    """基于 bge-reranker 系列交叉编码器的重排序。"""

    name = "cross-encoder"

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.reranker_model
        self._max_length = settings.reranker_max_length
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                    except ImportError as e:  # pragma: no cover
                        raise RuntimeError("sentence-transformers 未安装") from e
                    logger.info("加载 Reranker 模型: %s", self.model_name)
                    self._model = CrossEncoder(
                        self.model_name, max_length=self._max_length
                    )

    def rerank(self, query: str, chunks: list, top_n: int = 3) -> list:
        if not chunks:
            return []
        self._ensure_model()
        pairs = [(query, c.content) for c in chunks]
        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.exception("Reranker 推理失败, 回退向量相似度排序")
            return chunks[:top_n]
        ranked = sorted(zip(chunks, scores), key=lambda x: float(x[1]), reverse=True)
        results = []
        for chunk, score in ranked[:top_n]:
            chunk.rerank_score = round(float(score), 4)
            results.append(chunk)
        logger.info("Reranker 完成: %d → %d", len(chunks), len(results))
        return results


class NoopReranker(BaseReranker):
    """禁用重排序时的空实现。"""

    name = "noop"

    def rerank(self, query: str, chunks: list, top_n: int = 3) -> list:
        return chunks[:top_n]


def get_reranker() -> BaseReranker:
    """根据配置返回 Reranker 实例。"""
    settings = get_settings()
    if settings.reranker_enabled:
        return CrossEncoderReranker()
    return NoopReranker()
