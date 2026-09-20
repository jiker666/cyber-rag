"""RAG Pipeline: 完整问答链路编排(Security-Aware Adaptive RAG)。

自适应模式: 预处理 → 查询分析(规则) → 自适应路由 → 缓存感知检索(并行混合/
           实体加权/门控重排/小到大扩展) → 动态上下文预算 → LLM → 答案+引用+Trace
传统模式: 预处理 → 固定策略检索 → 上下文 → LLM(与历史版本行为一致, 供对照实验)
LLM Only:  预处理 → LLM 直接生成(对照组)
"""
import logging
import re
import time
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.llm.base import BaseLLM, LLMMessage
from app.llm.factory import get_llm_provider
from app.rag.adaptive import (
    CONFIDENCE_LABELS,
    RouteDecision,
    decide_route,
    retrieval_confidence,
    RetrievalSignals,
)
from app.rag.analyzer import QueryAnalysis, analyze_query
from app.rag.context_builder import build_context
from app.rag.context_optimizer import optimize_context
from app.rag.prompts import (
    DECOMPOSE_SYSTEM_PROMPT,
    LLM_ONLY_SYSTEM_PROMPT,
    LOW_EVIDENCE_ADDON,
    RAG_SYSTEM_PROMPT,
    RAG_USER_TEMPLATE,
    preprocess_query,
)
from app.rag.retriever import RetrievedChunk, Retriever, RetrievalMeta
from app.rag.trace import RagTrace

logger = logging.getLogger("cyber-rag.rag.pipeline")


@dataclass
class ChatHistoryItem:
    role: str  # user / assistant
    content: str


@dataclass
class RagParams:
    """一次问答使用的 RAG 参数(由调用方传入, 支撑对比实验与消融)。"""

    top_k: int | None = None
    temperature: float | None = None
    score_threshold: float | None = None
    enable_reranker: bool | None = None
    rerank_top_n: int | None = None
    retrieval_strategy: str | None = None
    history_window: int | None = None
    # ---- Adaptive RAG(消融实验开关; None = 跟随全局配置) ----
    adaptive: bool | None = None
    entity_boost: bool | None = None
    rerank_gating: bool | None = None  # False = 关闭门控, 回退固定重排开关(消融)
    dynamic_context: bool | None = None
    use_caches: bool | None = None


@dataclass
class PipelineResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    retrieval_time: int = 0  # ms
    generation_time: int = 0  # ms
    total_time: int = 0  # ms
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    retrieved_count: int = 0
    trace: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)
    route: dict = field(default_factory=dict)
    confidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "retrievalTime": self.retrieval_time,
            "generationTime": self.generation_time,
            "totalTime": self.total_time,
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "totalTokens": self.total_tokens,
            "retrievedCount": self.retrieved_count,
            "trace": self.trace,
            "analysis": self.analysis,
            "route": self.route,
            "confidence": self.confidence,
        }


class RagPipeline:
    """RAG 问答编排器(依赖注入, 便于测试)。"""

    def __init__(self, retriever: Retriever | None = None, llm: BaseLLM | None = None):
        self.retriever = retriever
        self.llm = llm

    def _get_retriever(self) -> Retriever:
        if self.retriever is None:
            self.retriever = Retriever()
        return self.retriever

    def _get_llm(self) -> BaseLLM:
        if self.llm is None:
            self.llm = get_llm_provider()
        return self.llm

    # ------------------------------------------------------------------
    # 参数归并
    # ------------------------------------------------------------------
    @staticmethod
    def _effective_params(params: RagParams) -> dict:
        settings = get_settings()
        return {
            "adaptive": params.adaptive if params.adaptive is not None else settings.adaptive_enabled,
            "entity_boost": params.entity_boost if params.entity_boost is not None else settings.entity_boost_enabled,
            "rerank_gating": params.rerank_gating if params.rerank_gating is not None else True,
            "dynamic_context": params.dynamic_context if params.dynamic_context is not None else settings.adaptive_enabled,
            "use_caches": params.use_caches if params.use_caches is not None else settings.adaptive_enabled,
        }

    # ------------------------------------------------------------------
    # 多跳分解(严格门控: 仅 MULTI_HOP 且复杂度达阈值)
    # ------------------------------------------------------------------
    def _decompose(self, question: str) -> list[str]:
        try:
            result = self._get_llm().chat(
                messages=[
                    LLMMessage(role="system", content=DECOMPOSE_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=question),
                ],
                temperature=0.1,
                max_tokens=200,
            )
        except Exception:
            logger.warning("查询分解失败, 回退原始问题单路检索")
            return [question]
        subs = [
            re.sub(r"^[\d\.\-\s]+", "", line).strip()
            for line in result.content.splitlines()
            if line.strip() and len(line.strip()) >= 4
        ]
        return subs[:3] or [question]

    def _multi_hop_retrieve(
        self,
        question: str,
        sub_queries: list[str],
        knowledge_base_ids: list[int],
        params: RagParams,
        decision: RouteDecision,
        analysis: QueryAnalysis,
        meta: RetrievalMeta,
        trace: RagTrace,
    ) -> list[RetrievedChunk]:
        """子查询并行检索 → RRF 跨子查询融合 → 单次强制重排。"""
        retriever = self._get_retriever()
        per_sub_k = 3
        sub_results: list[list[RetrievedChunk]] = []
        for sub in sub_queries:  # 线程池由 retriever 内部并发; 子查询间串行避免打满 CPU
            chunks = retriever.retrieve(
                sub,
                knowledge_base_ids,
                top_k=per_sub_k,
                score_threshold=params.score_threshold,
                retrieval_strategy="hybrid",
                enable_reranker=False,
                trace=trace,
                meta=None,
            )
            sub_results.append(chunks)

        # 跨子查询 RRF 融合(按子查询内排名)
        fused: dict[tuple, dict] = {}
        for chunks in sub_results:
            for rank, chunk in enumerate(chunks, start=1):
                key = (chunk.knowledge_base_id, chunk.document_id, chunk.chunk_index)
                if key in fused:
                    fused[key]["rrf"] += 1.0 / (60 + rank)
                else:
                    fused[key] = {"chunk": chunk, "rrf": 1.0 / (60 + rank)}
        merged = [item["chunk"] for item in sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)]
        for item in merged:
            item.rrf_score = item.rrf_score or 0.0
        meta.candidate_count = len(merged)
        trace.candidate_count = len(merged)

        # 单次强制重排(合并候选统一精排)
        t3 = time.perf_counter()
        reranker = retriever._default_reranker or _get_enabled_reranker()
        results = reranker.rerank(question, merged, top_n=decision.top_k)
        meta.rerank_ms = int((time.perf_counter() - t3) * 1000)
        meta.reranker_used = True
        meta.rerank_reason = "多跳合并候选强制重排"
        trace.rerank_ms = meta.rerank_ms
        trace.reranker_used = True
        trace.rerank_reason = meta.rerank_reason
        if results:
            meta.top1_score = results[0].rerank_score
            meta.score_margin = None
        return results

    # ------------------------------------------------------------------
    # 检索(统一入口, 自适应/传统共用)
    # ------------------------------------------------------------------
    def _retrieve(
        self,
        query: str,
        knowledge_base_ids: list[int],
        params: RagParams,
        analysis: QueryAnalysis,
        decision: RouteDecision | None,
        eff: dict,
        trace: RagTrace,
        meta: RetrievalMeta,
    ) -> tuple[list[RetrievedChunk], RouteDecision | None]:
        retriever = self._get_retriever()

        if decision is not None and decision.need_decompose:
            sub_queries = self._decompose(query)
            logger.info("多跳分解: %s → %s", query[:30], sub_queries)
            chunks = self._multi_hop_retrieve(
                query, sub_queries, knowledge_base_ids, params, decision, analysis, meta, trace
            )
            return chunks, decision

        if decision is not None and not eff["rerank_gating"]:
            # 消融(-Reranker Gating): 门控回退为固定开关(force/skip), 路由策略保持不变
            if params.enable_reranker is True:
                decision.rerank_policy = "force"
            elif params.enable_reranker is False:
                decision.rerank_policy = "skip"

        chunks = retriever.retrieve(
            query,
            knowledge_base_ids,
            top_k=params.top_k,
            score_threshold=params.score_threshold,
            enable_reranker=params.enable_reranker,
            rerank_top_n=params.rerank_top_n,
            retrieval_strategy=params.retrieval_strategy,
            analysis=analysis if decision else None,
            decision=decision,
            use_caches=eff["use_caches"],
            entity_boost=eff["entity_boost"],
            trace=trace,
            meta=meta,
        )
        if decision is not None:
            # 检索内部可能变更决策(FAST 置信不足升级 HYBRID), 同步到 Trace
            trace.route = decision.route
            trace.route_reason = decision.reason
        return chunks, decision

    # ------------------------------------------------------------------
    # 证据置信度
    # ------------------------------------------------------------------
    @staticmethod
    def _confidence(meta: RetrievalMeta, top_k: int) -> dict:
        signals = RetrievalSignals(
            top1_score=meta.top1_score,
            top2_score=meta.top2_score,
            score_margin=meta.score_margin,
            agreement=meta.agreement,
            candidate_count=meta.candidate_count,
            rerank_top1=meta.top1_score if meta.reranker_used else None,
        )
        conf, level = retrieval_confidence(signals, top_k)
        return {
            "retrievalConfidence": conf,
            "level": level,
            "label": CONFIDENCE_LABELS[level],
            "top1Score": meta.top1_score,
            "scoreMargin": meta.score_margin,
            "agreement": meta.agreement,
            "sourceCount": meta.candidate_count,
        }

    # ------------------------------------------------------------------
    # RAG 问答(同步; 流式见 rag_chat_stream)
    # ------------------------------------------------------------------
    def rag_chat(
        self,
        question: str,
        knowledge_base_ids: list[int],
        params: RagParams | None = None,
        history: list[ChatHistoryItem] | None = None,
    ) -> PipelineResult:
        params = params or RagParams()
        settings = get_settings()
        eff = self._effective_params(params)
        trace = RagTrace()
        total_start = time.perf_counter()

        # 1. 查询预处理
        query = preprocess_query(question)
        if not query:
            from app.core.errors import RagServiceError

            raise RagServiceError(422, "问题内容为空")

        # 2. 查询分析(规则, 亚毫秒; 自适应与否都执行, 供 Trace/实验统计)
        with trace.stage("query_analysis_ms"):
            analysis = analyze_query(query)
        trace.query_type = analysis.query_type

        # 3. 自适应路由
        decision = decide_route(analysis) if eff["adaptive"] else None
        if decision is not None:
            trace.route = decision.route
            trace.route_reason = decision.reason
        effective_k = (params.top_k or (decision.top_k if decision else settings.default_top_k))

        # 4-5. 检索(缓存/并行/加权/门控/小到大)
        meta = RetrievalMeta()
        retrieve_start = time.perf_counter()
        chunks: list[RetrievedChunk] = []
        if knowledge_base_ids:
            chunks, decision = self._retrieve(
                query, [int(k) for k in knowledge_base_ids], params, analysis, decision, eff, trace, meta
            )
        retrieval_time = int((time.perf_counter() - retrieve_start) * 1000)

        # 6. 动态上下文预算(自适应默认开启; 消融可关闭)
        context_start = time.perf_counter()
        if chunks and eff["dynamic_context"]:
            selection = optimize_context(chunks, analysis)
            chunks = selection.chunks
            trace.context_tokens = selection.context_tokens
            trace.dropped_chunks = (
                selection.dropped_duplicates + selection.dropped_by_budget
            )
        elif chunks:
            from app.rag.context_optimizer import estimate_tokens

            trace.context_tokens = sum(estimate_tokens(c.content) for c in chunks)
        trace.context_build_ms = int((time.perf_counter() - context_start) * 1000)
        trace.final_context_count = len(chunks)

        # 7. 证据置信度 + 低证据强约束
        confidence = self._confidence(meta, effective_k) if chunks else {
            "retrievalConfidence": 0.0, "level": "insufficient", "label": CONFIDENCE_LABELS["insufficient"],
            "top1Score": None, "scoreMargin": None, "agreement": None, "sourceCount": 0,
        }
        trace.retrieval_confidence = confidence["retrievalConfidence"]
        trace.confidence_level = confidence["level"]

        # 8. 上下文与 Prompt 构造
        context = build_context(chunks)
        user_content = RAG_USER_TEMPLATE.format(
            context=context or "(知识库中未检索到相关内容)", question=query
        )
        if chunks and confidence["level"] == "insufficient":
            user_content += LOW_EVIDENCE_ADDON

        window = params.history_window if params.history_window is not None else settings.default_history_window
        messages = [LLMMessage(role="system", content=RAG_SYSTEM_PROMPT)]
        if history:
            for item in history[-window:]:
                messages.append(LLMMessage(role=item.role, content=item.content[:2000]))
        messages.append(LLMMessage(role="user", content=user_content))

        # 9. LLM 生成
        generate_start = time.perf_counter()
        llm_result = self._get_llm().chat(
            messages=messages, temperature=params.temperature or settings.default_temperature
        )
        generation_time = int((time.perf_counter() - generate_start) * 1000)
        trace.generation_ms = generation_time
        trace.total_ms = int((time.perf_counter() - total_start) * 1000)

        logger.info(
            "RAG 问答完成: 类型=%s, 路由=%s, 命中=%d→%d, 检索=%dms, 生成=%dms, 总耗时=%dms",
            analysis.query_type, trace.route, meta.candidate_count, len(chunks),
            retrieval_time, generation_time, trace.total_ms,
        )
        return PipelineResult(
            answer=llm_result.content,
            sources=[c.to_dict() for c in chunks],
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            total_time=trace.total_ms,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            retrieved_count=len(chunks),
            trace=trace.to_dict(),
            analysis=analysis.to_dict(),
            route=decision.to_dict() if decision else {},
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # RAG 问答(流式): 产出事件流供 SSE 转发
    # ------------------------------------------------------------------
    def rag_chat_stream(
        self,
        question: str,
        knowledge_base_ids: list[int],
        params: RagParams | None = None,
        history: list[ChatHistoryItem] | None = None,
    ):
        """同步生成器: 依次产出
        {"type":"analysis", analysis, route}
        {"type":"retrieval", sources, confidence}
        {"type":"delta", text} ×N
        {"type":"done", result(PipelineResult.to_dict)}
        由 FastAPI StreamingResponse 在线程池中迭代。
        """
        params = params or RagParams()
        settings = get_settings()
        eff = self._effective_params(params)
        trace = RagTrace()
        total_start = time.perf_counter()

        query = preprocess_query(question)
        if not query:
            from app.core.errors import RagServiceError

            raise RagServiceError(422, "问题内容为空")

        with trace.stage("query_analysis_ms"):
            analysis = analyze_query(query)
        trace.query_type = analysis.query_type
        decision = decide_route(analysis) if eff["adaptive"] else None
        if decision is not None:
            trace.route = decision.route
            trace.route_reason = decision.reason
        effective_k = params.top_k or (decision.top_k if decision else settings.default_top_k)
        yield {"type": "analysis", "analysis": analysis.to_dict(),
               "route": decision.to_dict() if decision else {}}

        meta = RetrievalMeta()
        retrieve_start = time.perf_counter()
        chunks: list[RetrievedChunk] = []
        if knowledge_base_ids:
            chunks, decision = self._retrieve(
                query, [int(k) for k in knowledge_base_ids], params, analysis, decision, eff, trace, meta
            )
        retrieval_time = int((time.perf_counter() - retrieve_start) * 1000)

        context_start = time.perf_counter()
        if chunks and eff["dynamic_context"]:
            selection = optimize_context(chunks, analysis)
            chunks = selection.chunks
            trace.context_tokens = selection.context_tokens
            trace.dropped_chunks = selection.dropped_duplicates + selection.dropped_by_budget
        elif chunks:
            from app.rag.context_optimizer import estimate_tokens

            trace.context_tokens = sum(estimate_tokens(c.content) for c in chunks)
        trace.context_build_ms = int((time.perf_counter() - context_start) * 1000)
        trace.final_context_count = len(chunks)

        confidence = self._confidence(meta, effective_k) if chunks else {
            "retrievalConfidence": 0.0, "level": "insufficient", "label": CONFIDENCE_LABELS["insufficient"],
            "top1Score": None, "scoreMargin": None, "agreement": None, "sourceCount": 0,
        }
        trace.retrieval_confidence = confidence["retrievalConfidence"]
        trace.confidence_level = confidence["level"]
        yield {"type": "retrieval", "sources": [c.to_dict() for c in chunks], "confidence": confidence}

        context = build_context(chunks)
        user_content = RAG_USER_TEMPLATE.format(
            context=context or "(知识库中未检索到相关内容)", question=query
        )
        if chunks and confidence["level"] == "insufficient":
            user_content += LOW_EVIDENCE_ADDON

        window = params.history_window if params.history_window is not None else settings.default_history_window
        messages = [LLMMessage(role="system", content=RAG_SYSTEM_PROMPT)]
        if history:
            for item in history[-window:]:
                messages.append(LLMMessage(role=item.role, content=item.content[:2000]))
        messages.append(LLMMessage(role="user", content=user_content))

        # LLM 流式生成(TTFT 记入 trace)
        answer_parts: list[str] = []
        prompt_tokens = completion_tokens = 0
        generate_start = time.perf_counter()
        for event in self._get_llm().chat_stream(
            messages=messages, temperature=params.temperature or settings.default_temperature
        ):
            if event["type"] == "delta":
                answer_parts.append(event["text"])
                yield {"type": "delta", "text": event["text"]}
            elif event["type"] == "usage":
                prompt_tokens = event.get("prompt_tokens", 0)
                completion_tokens = event.get("completion_tokens", 0)
                if event.get("ttft_ms"):
                    trace.llm_ttft_ms = event["ttft_ms"]
        generation_time = int((time.perf_counter() - generate_start) * 1000)
        trace.generation_ms = generation_time
        trace.total_ms = int((time.perf_counter() - total_start) * 1000)

        answer = "".join(answer_parts)
        if not answer.strip():
            # 零正文落库无意义(典型成因: GLM thinking 耗尽 max_tokens 预算, 见 llm provider 告警日志);
            # 改发 error 事件, 由调用方(前端/评测)显式感知, 不静默持久化空答案
            logger.warning(
                "流式生成零正文: 类型=%s, 路由=%s, completion_tokens=%d",
                analysis.query_type, trace.route, completion_tokens,
            )
            yield {
                "type": "error",
                "message": "模型未返回内容(推理可能耗尽输出预算), 请重试或简化问题",
            }
            return
        logger.info(
            "RAG 流式问答完成: 类型=%s, 路由=%s, 上下文=%d, TTFT=%dms, 生成=%dms, 总耗时=%dms",
            analysis.query_type, trace.route, len(chunks), trace.llm_ttft_ms,
            generation_time, trace.total_ms,
        )
        result = PipelineResult(
            answer=answer,
            sources=[c.to_dict() for c in chunks],
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            total_time=trace.total_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            retrieved_count=len(chunks),
            trace=trace.to_dict(),
            analysis=analysis.to_dict(),
            route=decision.to_dict() if decision else {},
            confidence=confidence,
        )
        yield {"type": "done", "result": result.to_dict()}

    # ------------------------------------------------------------------
    def llm_only_chat(
        self, question: str, params: RagParams | None = None
    ) -> PipelineResult:
        """对照组: 不检索, 直接由 LLM 生成。"""
        params = params or RagParams()
        settings = get_settings()
        trace = RagTrace()
        total_start = time.perf_counter()

        query = preprocess_query(question)
        with trace.stage("query_analysis_ms"):
            analysis = analyze_query(query)  # 仅记录, 不影响行为
        trace.query_type = analysis.query_type
        messages = [
            LLMMessage(role="system", content=LLM_ONLY_SYSTEM_PROMPT),
            LLMMessage(role="user", content=query),
        ]
        generate_start = time.perf_counter()
        llm_result = self._get_llm().chat(
            messages=messages, temperature=params.temperature or settings.default_temperature
        )
        generation_time = int((time.perf_counter() - generate_start) * 1000)
        trace.generation_ms = generation_time
        trace.total_ms = int((time.perf_counter() - total_start) * 1000)
        logger.info("LLM Only 问答完成: 生成=%dms, 总耗时=%dms", generation_time, trace.total_ms)
        return PipelineResult(
            answer=llm_result.content,
            sources=[],
            retrieval_time=0,
            generation_time=generation_time,
            total_time=trace.total_ms,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            retrieved_count=0,
            trace=trace.to_dict(),
            analysis=analysis.to_dict(),
        )


def _get_enabled_reranker():
    from app.rag.reranker import get_reranker

    return get_reranker(enabled=True)
