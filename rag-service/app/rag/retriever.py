"""检索器: 查询向量化 → Chroma 多知识库检索 → 阈值过滤 → (可选 BM25+RRF 混合) → (可选重排序)。"""
import logging
import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.embedding.base import BaseEmbedding
from app.rag.reranker import get_reranker, BaseReranker
from app.vectorstore.chroma_store import ChromaStore, get_vector_store
from app.embedding.factory import get_embedding_provider

logger = logging.getLogger("cyber-rag.rag.retriever")

# RRF(Reciprocal Rank Fusion) 平滑常数
RRF_K = 60


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
    score: float | None = None  # 余弦相似度; BM25 独有命中无余弦分时为 None
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
        retrieval_strategy: str | None = None,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        k = top_k or settings.default_top_k
        threshold = (
            score_threshold if score_threshold is not None else settings.default_score_threshold
        )
        use_rerank = (
            enable_reranker if enable_reranker is not None else settings.reranker_enabled
        )
        strategy = retrieval_strategy or settings.retrieval_strategy
        if strategy not in ("vector", "hybrid"):
            strategy = "vector"

        start = time.perf_counter()
        query_embedding = self.embedding.embed_query(query)
        candidates: list[RetrievedChunk] = []
        # Reranker / Hybrid 需要更大候选池
        recall_k = k * 4 if (use_rerank or strategy == "hybrid") else k
        for kb_id in knowledge_base_ids:
            hits = self.store.query(int(kb_id), query_embedding, top_k=recall_k)
            # 阈值过滤(混合模式下向量候选同样先过阈值, 保持"无知识拒答"语义)
            hits = [h for h in hits if h["score"] >= threshold]
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

        if strategy == "hybrid" and knowledge_base_ids:
            candidates = self._hybrid_fuse(query, knowledge_base_ids, candidates, recall_k)

        # 多知识库结果按相似度归并(混合模式已按 RRF 分排序)
        if strategy != "hybrid":
            candidates.sort(key=lambda c: c.score or 0.0, reverse=True)
            candidates = candidates[:recall_k]

        # 可选重排序
        if use_rerank and candidates:
            reranker = self._default_reranker or get_reranker()
            keep = rerank_top_n or settings.default_top_k
            candidates = reranker.rerank(query, candidates, top_n=keep)

        results = candidates[:k]
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.info(
            "检索完成: query=%r, kb=%s, 策略=%s, 候选=%d, 返回=%d, 耗时=%dms",
            query[:30], knowledge_base_ids, strategy, len(candidates), len(results), elapsed,
        )
        return results

    def _hybrid_fuse(
        self,
        query: str,
        knowledge_base_ids: list[int],
        vector_chunks: list[RetrievedChunk],
        recall_k: int,
    ) -> list[RetrievedChunk]:
        """BM25 + 向量 RRF 融合: score = Σ 1/(k + rank_i)。

        - 向量候选已在阈值过滤后传入, 按 chunk 唯一键参与融合
        - BM25 命中(可能无余弦分)补充精确词召回, score 置 None
        """
        from app.rag.bm25 import get_bm25_store

        bm25_store = get_bm25_store(self.store)
        fused: dict[tuple, dict] = {}

        def _key(c: RetrievedChunk) -> tuple:
            return (c.knowledge_base_id, c.document_id, c.chunk_index)

        # 向量侧排名(按余弦分)
        for rank, chunk in enumerate(
            sorted(vector_chunks, key=lambda c: c.score or 0.0, reverse=True), start=1
        ):
            fused[_key(chunk)] = {"chunk": chunk, "rrf": 1.0 / (RRF_K + rank)}

        # BM25 侧排名(逐知识库)
        for kb_id in knowledge_base_ids:
            for rank, hit in enumerate(
                bm25_store.search(int(kb_id), query, top_n=recall_k), start=1
            ):
                meta = hit["metadata"]
                key = (
                    int(kb_id),
                    int(meta.get("document_id", 0)),
                    int(meta.get("chunk_index", 0)),
                )
                rrf = 1.0 / (RRF_K + rank)
                if key in fused:
                    fused[key]["rrf"] += rrf
                else:
                    fused[key] = {
                        "chunk": RetrievedChunk(
                            content=hit["content"],
                            document_id=int(meta.get("document_id", 0)),
                            document_name=str(meta.get("document_name", "未知文档")),
                            knowledge_base_id=int(meta.get("knowledge_base_id", kb_id)),
                            chunk_index=int(meta.get("chunk_index", 0)),
                            source=str(meta.get("source", "")),
                            page=meta.get("page"),
                            score=None,  # BM25 独有命中, 无余弦相似度
                        ),
                        "rrf": rrf,
                    }

        ranked = sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)
        return [item["chunk"] for item in ranked]
