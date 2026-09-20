"""检索器: 查询向量化 → Chroma 多知识库检索 → 阈值过滤 → (并行 BM25+RRF 混合)
→ (实体精确加权) → (置信度门控重排) → (小到大父块扩展)。

混合检索中 Vector 与 BM25 互不依赖, 通过线程池并发执行(Chroma 原生查询释放 GIL,
BM25 为纯 Python 计算, 并发可真实降低墙钟耗时, 见 E5 benchmark 实测)。

缓存口径: RetrievalCache 缓存"融合后候选"(重排不在缓存内 —— 门控与 CrossEncoder
每次基于候选真实执行, 保证 rerank activation 统计与排序行为一致)。
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields as dc_fields

from app.core.config import get_settings
from app.embedding.base import BaseEmbedding
from app.rag.reranker import get_reranker, BaseReranker
from app.vectorstore.chroma_store import ChromaStore, get_vector_store
from app.embedding.factory import get_embedding_provider

logger = logging.getLogger("cyber-rag.rag.retriever")

# RRF(Reciprocal Rank Fusion) 平滑常数
RRF_K = 60
# 精确实体确定性加权: 约等于"额外一次第 1 名"的 RRF 加成(1/61≈0.0164)的 1.8 倍,
# 保证含 CVE/CWE 编号的片段稳定优先于语义相近但无编号的片段
ENTITY_BOOST_RRF = 0.03

# 混合检索并发线程池(进程级复用)
_fusion_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hybrid-ret")


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
    match_type: str = "vector"  # vector | bm25 | both(双路共同命中)
    entity_matched: bool = False  # 命中查询中的精确安全实体编号
    parent_chunk_id: int | None = None  # 小到大: 父块编号(父块入库时写入子块元数据)
    parent_text: str | None = None  # 小到大: 父块全文(入库时写入子块元数据, 不序列化)
    rrf_score: float | None = None  # 混合融合分(调试/实验用)

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
            "matchType": self.match_type,
            "entityMatched": self.entity_matched,
            "parentChunkId": self.parent_chunk_id,
        }


@dataclass
class RetrievalMeta:
    """检索阶段的信号与决策记录(门控/置信度/Trace 的数据源)。"""

    strategy: str = "vector"
    vector_ms: int = 0
    bm25_ms: int = 0
    fusion_ms: int = 0
    rerank_ms: int = 0
    candidate_count: int = 0
    top1_score: float | None = None
    top2_score: float | None = None
    score_margin: float | None = None
    agreement: float | None = None  # vector/BM25 Top-5 重合率(单路为 None)
    reranker_used: bool = False
    rerank_reason: str = ""
    entity_boosted: bool = False
    entity_matched_count: int = 0
    fast_escalated: bool = False  # FAST 路径置信不足升级为混合
    embedding_cache_hit: bool = False
    retrieval_cache_hit: bool = False
    small_to_large: bool = False  # 本次检索发生了子→父扩展
    parent_expanded: int = 0  # 去重合并的子块数


def _chunk_key(c: RetrievedChunk) -> tuple:
    return (c.knowledge_base_id, c.document_id, c.chunk_index)


def _chunk_from_hit(hit: dict, kb_id: int, match_type: str = "vector") -> RetrievedChunk:
    meta = hit["metadata"]
    parent_id = meta.get("parent_chunk_id")
    return RetrievedChunk(
        content=hit["content"],
        document_id=int(meta.get("document_id", 0)),
        document_name=str(meta.get("document_name", "未知文档")),
        knowledge_base_id=int(meta.get("knowledge_base_id", kb_id)),
        chunk_index=int(meta.get("chunk_index", 0)),
        source=str(meta.get("source", "")),
        page=meta.get("page"),
        score=float(hit["score"]) if match_type == "vector" else None,
        match_type=match_type,
        parent_chunk_id=int(parent_id) if parent_id is not None else None,
        parent_text=str(meta["parent_text"]) if meta.get("parent_text") else None,
    )


def _infer_top1_score(candidates: list[RetrievedChunk]) -> float | None:
    """BM25 独有命中无余弦分: 以 RRF 分映射为弱信号(≤0.5, 保持门控保守倾向重排)。"""
    if not candidates:
        return None
    rrf = candidates[0].rrf_score
    return round(min((rrf or 0.0) * 30.0, 0.5), 4) if rrf is not None else None


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

    # ------------------------------------------------------------------
    # 查询向量化(带 LRU 缓存)
    # ------------------------------------------------------------------
    def _embed_query(self, query: str, use_caches: bool) -> tuple[list[float], bool]:
        if not use_caches:
            return self.embedding.embed_query(query), False
        from app.rag.caches import get_embedding_cache

        cache = get_embedding_cache()
        model = str(getattr(self.embedding, "model_name", "") or get_settings().embedding_model)
        cached = cache.get(query, model)
        if cached is not None:
            return cached, True
        vec = self.embedding.embed_query(query)
        cache.put(query, model, vec)
        return vec, False

    # ------------------------------------------------------------------
    # 单路检索
    # ------------------------------------------------------------------
    def _search_vector(
        self, kb_ids: list[int], query_embedding: list[float], recall_k: int, threshold: float
    ) -> list[RetrievedChunk]:
        candidates: list[RetrievedChunk] = []
        for kb_id in kb_ids:
            hits = self.store.query(int(kb_id), query_embedding, top_k=recall_k)
            hits = [h for h in hits if h["score"] >= threshold]  # 保持"无知识拒答"语义
            candidates.extend(_chunk_from_hit(h, kb_id, "vector") for h in hits)
        candidates.sort(key=lambda c: c.score or 0.0, reverse=True)
        return candidates[:recall_k]

    def _search_bm25(self, kb_ids: list[int], query: str, recall_k: int) -> list[RetrievedChunk]:
        from app.rag.bm25 import get_bm25_store

        bm25_store = get_bm25_store(self.store if self._custom_store else None)
        candidates: list[RetrievedChunk] = []
        for kb_id in kb_ids:
            for hit in bm25_store.search(int(kb_id), query, top_n=recall_k):
                candidates.append(_chunk_from_hit(hit, kb_id, "bm25"))
        return candidates

    # ------------------------------------------------------------------
    # RRF 融合 + 实体加权 + 一致性信号
    # ------------------------------------------------------------------
    @staticmethod
    def _fuse(
        vector_chunks: list[RetrievedChunk],
        bm25_chunks: list[RetrievedChunk],
        exact_identifiers: list[str],
        apply_entity_boost: bool,
    ) -> tuple[list[RetrievedChunk], float | None]:
        fused: dict[tuple, dict] = {}
        vector_top5 = {_chunk_key(c) for c in vector_chunks[:5]}
        bm25_top5 = {_chunk_key(c) for c in bm25_chunks[:5]}

        for rank, chunk in enumerate(vector_chunks, start=1):
            fused[_chunk_key(chunk)] = {"chunk": chunk, "rrf": 1.0 / (RRF_K + rank)}
        for rank, chunk in enumerate(bm25_chunks, start=1):
            key = _chunk_key(chunk)
            rrf = 1.0 / (RRF_K + rank)
            if key in fused:
                fused[key]["rrf"] += rrf
                fused[key]["chunk"].match_type = "both"
            else:
                fused[key] = {"chunk": chunk, "rrf": rrf}

        # 精确实体加权: 内容包含查询中的 CVE/CWE/ATT&CK 等编号 → 确定性 RRF 加成
        if apply_entity_boost and exact_identifiers:
            ids_upper = [i.upper() for i in exact_identifiers]
            for item in fused.values():
                content_upper = item["chunk"].content.upper()
                if any(i in content_upper for i in ids_upper):
                    item["rrf"] += ENTITY_BOOST_RRF
                    item["chunk"].entity_matched = True

        ranked = sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)
        for item in ranked:
            item["chunk"].rrf_score = round(item["rrf"], 6)
        chunks = [item["chunk"] for item in ranked]

        # 双路一致性: Top-5 重合率
        agreement = None
        if bm25_chunks:
            denom = max(len(vector_top5), len(bm25_top5), 1)
            agreement = round(len(vector_top5 & bm25_top5) / denom, 4)
        return chunks, agreement

    # ------------------------------------------------------------------
    # 小到大: 子块 → 父块扩展去重
    # ------------------------------------------------------------------
    @staticmethod
    def _expand_to_parents(chunks: list[RetrievedChunk]) -> tuple[list[RetrievedChunk], int]:
        """子块检索, 父块生成: 按 parent_chunk_id 去重。

        内容已在入库时写入子块元数据(parent_text), 命中子块替换为父块全文;
        引用仍对应原文档(文档名/页码保留), parent_chunk_id 可回溯父块。
        """
        by_parent: dict[tuple, RetrievedChunk] = {}
        for chunk in chunks:
            if chunk.parent_chunk_id is None:
                by_parent.setdefault(("raw", id(chunk)), chunk)
                continue
            key = (chunk.knowledge_base_id, chunk.document_id, chunk.parent_chunk_id)
            existing = by_parent.get(key)
            if existing is None or (chunk.rrf_score or 0) > (existing.rrf_score or 0):
                by_parent[key] = chunk
        merged_count = max(len(chunks) - len(by_parent), 0)
        # 子块内容 → 父块全文(检索用小块, 生成用大块)
        for parent in by_parent.values():
            if parent.parent_chunk_id is not None and parent.parent_text:
                parent.content = parent.parent_text
        return list(by_parent.values()), merged_count

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[int],
        top_k: int | None = None,
        score_threshold: float | None = None,
        enable_reranker: bool | None = None,
        rerank_top_n: int | None = None,
        retrieval_strategy: str | None = None,
        *,
        analysis=None,
        decision=None,
        use_caches: bool | None = None,
        entity_boost: bool | None = None,
        trace=None,
        meta: RetrievalMeta | None = None,
    ) -> list[RetrievedChunk]:
        """统一检索入口。

        - 传统模式(analysis/decision 为 None): 固定策略 + 重排开关, 与历史版本一致。
        - 自适应模式(传入 decision): 按路由执行, FAST 置信不足自动升级混合,
          重排由置信度门控(adaptive.should_rerank)决定。
        - use_caches 默认 False(测试隔离), 由 Pipeline 按全局配置传入。
        """
        settings = get_settings()
        meta = meta or RetrievalMeta()
        kb_ids = [int(k) for k in knowledge_base_ids]
        adaptive = decision is not None
        caches = bool(use_caches)

        if adaptive:
            strategy = decision.strategy
            k = top_k or decision.top_k
        else:
            k = top_k or settings.default_top_k
            strategy = retrieval_strategy or settings.retrieval_strategy
            if strategy not in ("vector", "hybrid"):
                strategy = "vector"
        threshold = (
            score_threshold if score_threshold is not None else settings.default_score_threshold
        )
        meta.strategy = strategy
        identifiers = list(analysis.exact_identifiers) if analysis else []
        apply_boost = (
            (entity_boost if entity_boost is not None else settings.entity_boost_enabled)
            and bool(identifiers)
            and strategy == "hybrid"
        )

        candidates: list[RetrievedChunk] = []

        if not kb_ids:
            return self._finish([], meta, trace, None)

        # ---- 检索缓存(版本感知, 缓存融合候选; 门控/重排不缓存) ----
        cache_key = None
        if caches:
            from app.rag.caches import get_retrieval_cache, get_kb_version_registry

            registry = get_kb_version_registry(self.store if self._custom_store else None)
            cache_key = get_retrieval_cache().build_key(
                kb_ids, registry.versions(kb_ids), query, strategy, k,
                apply_boost, False,
            )
            cached = get_retrieval_cache().get(cache_key)
            if cached is not None:
                cached_candidates, cached_meta = cached
                for f in ("vector_ms", "bm25_ms", "fusion_ms", "agreement", "embedding_cache_hit"):
                    setattr(meta, f, getattr(cached_meta, f))
                meta.retrieval_cache_hit = True
                meta.entity_boosted = cached_meta.entity_boosted
                candidates = cached_candidates
                logger.info("检索缓存命中: query=%r (%d 候选)", query[:30], len(candidates))

        rerank_top1 = None
        if meta.retrieval_cache_hit:
            # 缓存命中: 跳过检索, 仍执行 门控 → 重排 → 截断 → 扩展
            meta.candidate_count = len(candidates)
        else:
            # ---- 查询向量化(LRU 缓存) ----
            t0 = time.perf_counter()
            query_embedding, emb_hit = self._embed_query(query, caches)
            meta.embedding_cache_hit = emb_hit
            if trace is not None:
                trace.embedding_ms = int((time.perf_counter() - t0) * 1000)

            recall_k = k * 4 if strategy == "hybrid" else k
            if strategy == "hybrid":
                candidates = self._hybrid_search(
                    kb_ids, query, query_embedding, recall_k, threshold,
                    identifiers, apply_boost, meta,
                )
            else:
                t1 = time.perf_counter()
                candidates = self._search_vector(kb_ids, query_embedding, recall_k, threshold)
                meta.vector_ms = int((time.perf_counter() - t1) * 1000)
                meta.agreement = None
                # FAST 路径: 置信不足自动升级混合
                if adaptive and decision.route == "FAST" and candidates:
                    top1 = candidates[0].score or 0.0
                    top2 = (candidates[1].score or 0.0) if len(candidates) > 1 else 0.0
                    if top1 < settings.fast_path_top1_min or (top1 - top2) < settings.fast_path_margin_min:
                        meta.fast_escalated = True
                        decision.route = "HYBRID"
                        decision.strategy = "hybrid"
                        decision.rerank_policy = "auto"
                        decision.reason = (
                            f"FAST 升级: 向量置信不足(top1={top1:.3f}, margin={top1 - top2:.3f}), 转混合检索"
                        )
                        meta.strategy = "hybrid"
                        candidates = self._hybrid_search(
                            kb_ids, query, query_embedding, k * 4, threshold,
                            identifiers, apply_boost, meta,
                        )
            meta.candidate_count = len(candidates)

        # ---- Top 信号(门控输入) ----
        if candidates:
            meta.top1_score = (
                candidates[0].score if candidates[0].score is not None
                else _infer_top1_score(candidates)
            )
            if len(candidates) > 1:
                second = candidates[1]
                meta.top2_score = (
                    second.score if second.score is not None
                    else _infer_top1_score(candidates[1:])
                )
                meta.score_margin = round((meta.top1_score or 0.0) - (meta.top2_score or 0.0), 4)

        # ---- 重排决策: 传统开关 vs 置信度门控 ----
        if adaptive:
            from app.rag.adaptive import RetrievalSignals, should_rerank

            signals = RetrievalSignals(
                top1_score=meta.top1_score,
                top2_score=meta.top2_score,
                score_margin=meta.score_margin,
                agreement=meta.agreement,
                candidate_count=meta.candidate_count,
            )
            use_rerank, reason = should_rerank(decision, analysis, signals)
            meta.rerank_reason = reason
        else:
            use_rerank = (
                enable_reranker if enable_reranker is not None else settings.reranker_enabled
            )
            meta.rerank_reason = "固定开关(非自适应)"

        results = candidates
        if use_rerank and candidates:
            t3 = time.perf_counter()
            reranker = self._default_reranker or get_reranker(enabled=True)
            keep = rerank_top_n or settings.default_top_k
            results = reranker.rerank(query, candidates, top_n=max(keep, k))
            meta.rerank_ms = int((time.perf_counter() - t3) * 1000)
            meta.reranker_used = True
            if results:
                rerank_top1 = results[0].rerank_score
                meta.top1_score = rerank_top1  # 重排后以 CrossEncoder 分作为置信信号
                meta.score_margin = None
                meta.top2_score = None

        results = results[:k]

        # ---- 小到大父块扩展(候选含 parent 元数据时自动生效) ----
        if results and any(c.parent_chunk_id is not None for c in results):
            results, merged = self._expand_to_parents(results)
            meta.small_to_large = True
            meta.parent_expanded = merged

        self._log(query, kb_ids, meta, results)

        # ---- 写检索缓存(融合候选 + 元信号) ----
        if cache_key is not None and not meta.retrieval_cache_hit:
            from app.rag.caches import get_retrieval_cache

            stored = RetrievalMeta(**{f.name: getattr(meta, f.name) for f in dc_fields(RetrievalMeta)})
            get_retrieval_cache().put(cache_key, (candidates, stored))
        return self._finish(results, meta, trace, rerank_top1)

    # ------------------------------------------------------------------
    def _hybrid_search(
        self, kb_ids, query, query_embedding, recall_k, threshold,
        identifiers, apply_boost, meta: RetrievalMeta,
    ) -> list[RetrievedChunk]:
        """Vector ∥ BM25 并行 → RRF 融合(+实体加权)。耗时/一致性写入 meta。

        耗时口径: 两路各自记录"自任务派发到结果就绪"的墙钟(并行执行, 互不阻塞),
        二者都 ≤ 串行执行之和, 可直接用于并行收益分析。
        """
        t1 = time.perf_counter()
        fut_vec = _fusion_pool.submit(self._search_vector, kb_ids, query_embedding, recall_k, threshold)
        fut_bm25 = _fusion_pool.submit(self._search_bm25, kb_ids, query, recall_k)
        vector_chunks = fut_vec.result()
        vec_done = time.perf_counter()
        bm25_chunks = fut_bm25.result()
        bm25_done = time.perf_counter()
        meta.vector_ms = int((vec_done - t1) * 1000)
        meta.bm25_ms = int((bm25_done - t1) * 1000)
        t2 = time.perf_counter()
        candidates, agreement = self._fuse(vector_chunks, bm25_chunks, identifiers, apply_boost)
        meta.fusion_ms = int((time.perf_counter() - t2) * 1000)
        meta.agreement = agreement
        if apply_boost:
            meta.entity_boosted = True
            meta.entity_matched_count = sum(1 for c in candidates if c.entity_matched)
        return candidates

    def _finish(
        self, chunks: list[RetrievedChunk], meta: RetrievalMeta, trace, rerank_top1
    ) -> list[RetrievedChunk]:
        if trace is not None:
            trace.vector_search_ms = meta.vector_ms
            trace.bm25_search_ms = meta.bm25_ms
            trace.fusion_ms = meta.fusion_ms
            trace.rerank_ms = meta.rerank_ms
            trace.reranker_used = meta.reranker_used
            trace.rerank_reason = meta.rerank_reason
            trace.entity_boosted = meta.entity_boosted
            trace.embedding_cache_hit = meta.embedding_cache_hit
            trace.retrieval_cache_hit = meta.retrieval_cache_hit
            trace.candidate_count = meta.candidate_count
        if not chunks:
            logger.info("检索完成: 无候选(阈值过滤或知识库为空)")
        return chunks

    def _log(self, query, kb_ids, meta: RetrievalMeta, results) -> None:
        logger.info(
            "检索完成: query=%r, kb=%s, 策略=%s, 候选=%d, 返回=%d, vec=%dms, bm25=%dms, "
            "融合=%dms, 重排=%s(%dms), 实体加权=%s, top1=%s, agreement=%s",
            query[:30], kb_ids, meta.strategy, meta.candidate_count, len(results),
            meta.vector_ms, meta.bm25_ms, meta.fusion_ms,
            meta.reranker_used, meta.rerank_ms, meta.entity_boosted,
            meta.top1_score, meta.agreement,
        )

    @property
    def _custom_store(self) -> bool:
        """是否注入了自定义向量库(测试隔离: BM25/版本表也需隔离)。"""
        return self.store is not get_vector_store()
