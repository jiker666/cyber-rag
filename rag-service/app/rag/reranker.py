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
                    model_path = self._resolve_local_path(self.model_name)
                    logger.info("加载 Reranker 模型: %s (路径: %s)", self.model_name, model_path)
                    self._model = CrossEncoder(
                        model_path, max_length=self._max_length
                    )

    @staticmethod
    def _resolve_local_path(model_name: str) -> str:
        """优先解析本地 HF 缓存快照路径, 避免联网做 etag 检查(网络不通时会长时间挂起);
        缓存不存在时回退为模型名(由 HF Hub 正常下载)。"""
        import glob
        import os
        from app.core.config import get_settings
        settings = get_settings()
        if os.path.isdir(model_name):
            return model_name
        repo_dir = os.path.join(settings.model_dir, f"models--{model_name.replace('/', '--')}", "snapshots", "*")
        for snap in sorted(glob.glob(repo_dir)):
            if os.path.exists(os.path.join(snap, "config.json")):
                return snap
        return model_name

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


_cross_encoder_instance: "CrossEncoderReranker | None" = None


def get_reranker(enabled: bool | None = None) -> BaseReranker:
    """根据配置返回 Reranker 实例。

    enabled: 请求级开关, 显式传入时覆盖全局配置(RAG_RERANKER_ENABLED);
    None 时回落全局配置。检索器在已决定启用重排时应传 enabled=True。
    CrossEncoder 为进程级单例(模型加载约 3s, 逐请求重建会显著拖慢检索)。
    """
    global _cross_encoder_instance
    settings = get_settings()
    use = settings.reranker_enabled if enabled is None else enabled
    if use:
        if _cross_encoder_instance is None:
            _cross_encoder_instance = CrossEncoderReranker()
        return _cross_encoder_instance
    return NoopReranker()
