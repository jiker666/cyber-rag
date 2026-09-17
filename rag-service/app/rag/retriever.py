"""检索器: 查询向量化 → Chroma 多知识库检索 → 阈值过滤 → 可选重排序。"""
import logging
import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.embedding.base import BaseEmbedding
from app.rag.reranker import get_reranker, BaseReranker
from app.vectorstore.chroma_store import ChromaStore, get_vector_store
from app.embedding.factory import get_embedding_provider

logger = logging.getLogger("cyber-rag.rag.retriever")


@dataclass
class RetrievedChunk:
    """检索命中的知识片段。"""

    content: str
    document_id: int
    document_name: str
    knowledge_base_id: int
    chunk_index: int
    source: str
    page: int | None
    score: float
    rerank_score: float | None = None

    def to_dict(self) -> dict:
        return {
            "documentId": self.document_id,
            "documentName": self.document_name,
            "knowledgeBaseId": self.knowledge_base_id,
            "chunkIndex": self.chunk_index,
            "source": self.source,
            "page": self.page,
            "content": self.content,
            "score": self.score,
            "rerankScore": self.rerank_score,
        }


class Retriever:
    """向量检索器(与 Embedding/向量库解耦, 便于测试与替换)。"""

    def __init__(
        self,
        store: ChromaStore | None = None,
        embedding: BaseEmbedding | None = None,
        reranker: BaseReranker | None = None,
    ):
        self.store = store or get_vector_store()
        self.embedding = embedding or get_embedding_provider()
        self._default_reranker = reranker

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[int],
        top_k: int | None = None,
        score_threshold: float | None = None,
        enable_reranker: bool | None = None,
        rerank_top_n: int | None = None,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        k = top_k or settings.default_top_k
        threshold = (
            score_threshold if score_threshold is not None else settings.default_score_threshold
        )
        use_rerank = (
            enable_reranker if enable_reranker is not None else settings.reranker_enabled
        )

        start = time.perf_counter()
        query_embedding = self.embedding.embed_query(query)
        candidates: list[RetrievedChunk] = []
        # Reranker 需要更大候选池
        recall_k = k * 4 if use_rerank else k
        for kb_id in knowledge_base_ids:
            hits = self.store.query(int(kb_id), query_embedding, top_k=recall_k)
            for hit in hits:
                meta = hit["metadata"]
                candidates.append(
                    RetrievedChunk(
                        content=hit["content"],
                        document_id=int(meta.get("document_id", 0)),
                        document_name=str(meta.get("document_name", "未知文档")),
                        knowledge_base_id=int(meta.get("knowledge_base_id", kb_id)),
                        chunk_index=int(meta.get("chunk_index", 0)),
                        source=str(meta.get("source", "")),
                        page=meta.get("page"),
                        score=float(hit["score"]),
                    )
                )
        # 多知识库结果按相似度归并
        candidates.sort(key=lambda c: c.score, reverse=True)
        # 阈值过滤
        filtered = [c for c in candidates if c.score >= threshold][: recall_k]

        # 可选重排序
        if use_rerank and filtered:
            reranker = self._default_reranker or get_reranker()
            keep = rerank_top_n or settings.default_top_k
            filtered = reranker.rerank(query, filtered, top_n=keep)

        results = filtered[:k]
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.info(
            "检索完成: query=%r, kb=%s, 候选=%d, 阈值过滤后=%d, 返回=%d, 耗时=%dms",
            query[:30], knowledge_base_ids, len(candidates), len(filtered), len(results), elapsed,
        )
        return results
