"""RAG Performance Trace: 逐阶段计时与决策记录, 随响应返回(不影响用户界面)。

每次问答产生一份完整 Trace, 供:
- 前端"本次 RAG 决策"折叠面板展示
- 评测落库(route/rerank_used/context_tokens 等)
- E5/Ablation 实验的延迟分解分析
"""
import time
from contextlib import contextmanager


class RagTrace:
    """单次问答的性能与决策轨迹(字段与前端/论文口径一一对应)。"""

    def __init__(self) -> None:
        # 阶段耗时(ms)
        self.query_analysis_ms = 0
        self.embedding_ms = 0
        self.vector_search_ms = 0
        self.bm25_search_ms = 0
        self.fusion_ms = 0
        self.rerank_ms = 0
        self.context_build_ms = 0
        self.llm_ttft_ms = 0
        self.generation_ms = 0
        self.total_ms = 0
        # 自适应决策
        self.route = ""
        self.route_reason = ""
        self.query_type = ""
        self.reranker_used = False
        self.rerank_reason = ""
        self.entity_boosted = False
        self.embedding_cache_hit = False
        self.retrieval_cache_hit = False
        # 规模统计
        self.candidate_count = 0
        self.final_context_count = 0
        self.context_tokens = 0
        self.dropped_chunks = 0
        # 置信度
        self.retrieval_confidence: float | None = None
        self.confidence_level = ""

    @contextmanager
    def stage(self, attr: str):
        """计时上下文: with trace.stage("vector_search_ms"): ..."""
        start = time.perf_counter()
        try:
            yield
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            setattr(self, attr, ms)

    def to_dict(self) -> dict:
        return {
            "queryAnalysisMs": self.query_analysis_ms,
            "embeddingMs": self.embedding_ms,
            "vectorSearchMs": self.vector_search_ms,
            "bm25SearchMs": self.bm25_search_ms,
            "fusionMs": self.fusion_ms,
            "rerankMs": self.rerank_ms,
            "contextBuildMs": self.context_build_ms,
            "llmTtftMs": self.llm_ttft_ms,
            "generationMs": self.generation_ms,
            "totalMs": self.total_ms,
            "route": self.route,
            "routeReason": self.route_reason,
            "queryType": self.query_type,
            "rerankerUsed": self.reranker_used,
            "rerankReason": self.rerank_reason,
            "entityBoosted": self.entity_boosted,
            "embeddingCacheHit": self.embedding_cache_hit,
            "retrievalCacheHit": self.retrieval_cache_hit,
            "candidateCount": self.candidate_count,
            "finalContextCount": self.final_context_count,
            "contextTokens": self.context_tokens,
            "droppedChunks": self.dropped_chunks,
            "retrievalConfidence": self.retrieval_confidence,
            "confidenceLevel": self.confidence_level,
        }
