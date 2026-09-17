"""RAG Pipeline: 完整问答链路编排。

RAG 模式:  预处理 → Embedding → 检索 → (可选重排) → 上下文构造 → LLM → 答案+引用
LLM Only:  预处理 → LLM 直接生成(对照组)
"""
import logging
import time
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.llm.base import BaseLLM, LLMMessage
from app.llm.factory import get_llm_provider
from app.rag.context_builder import build_context
from app.rag.prompts import (
    LLM_ONLY_SYSTEM_PROMPT,
    RAG_SYSTEM_PROMPT,
    RAG_USER_TEMPLATE,
    preprocess_query,
)
from app.rag.retriever import RetrievedChunk, Retriever

logger = logging.getLogger("cyber-rag.rag.pipeline")


@dataclass
class ChatHistoryItem:
    role: str  # user / assistant
    content: str


@dataclass
class RagParams:
    """一次问答使用的 RAG 参数(由调用方传入, 支撑对比实验)。"""

    top_k: int | None = None
    temperature: float | None = None
    score_threshold: float | None = None
    enable_reranker: bool | None = None
    rerank_top_n: int | None = None
    retrieval_strategy: str | None = None
    history_window: int | None = None


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
    def rag_chat(
        self,
        question: str,
        knowledge_base_ids: list[int],
        params: RagParams | None = None,
        history: list[ChatHistoryItem] | None = None,
    ) -> PipelineResult:
        """RAG 增强问答。"""
        params = params or RagParams()
        settings = get_settings()
        total_start = time.perf_counter()

        # 1. 查询预处理
        query = preprocess_query(question)
        if not query:
            from app.core.errors import RagServiceError

            raise RagServiceError(422, "问题内容为空")

        # 2-4. 检索(含 Embedding 与可选重排)
        retrieve_start = time.perf_counter()
        chunks: list[RetrievedChunk] = []
        if knowledge_base_ids:
            chunks = self._get_retriever().retrieve(
                query=query,
                knowledge_base_ids=[int(k) for k in knowledge_base_ids],
                top_k=params.top_k,
                score_threshold=params.score_threshold,
                enable_reranker=params.enable_reranker,
                rerank_top_n=params.rerank_top_n,
                retrieval_strategy=params.retrieval_strategy,
            )
        retrieval_time = int((time.perf_counter() - retrieve_start) * 1000)

        # 5. 上下文构造
        context = build_context(chunks)

        # 6-7. Prompt 构造(系统提示 + 历史窗口 + 当前问题)
        window = params.history_window if params.history_window is not None else settings.default_history_window
        messages = [LLMMessage(role="system", content=RAG_SYSTEM_PROMPT)]
        if history:
            for item in history[-window:]:
                messages.append(LLMMessage(role=item.role, content=item.content[:2000]))
        messages.append(
            LLMMessage(
                role="user",
                content=RAG_USER_TEMPLATE.format(context=context or "(知识库中未检索到相关内容)", question=query),
            )
        )

        # 8. LLM 生成
        generate_start = time.perf_counter()
        llm_result = self._get_llm().chat(
            messages=messages, temperature=params.temperature or settings.default_temperature
        )
        generation_time = int((time.perf_counter() - generate_start) * 1000)
        total_time = int((time.perf_counter() - total_start) * 1000)

        logger.info(
            "RAG 问答完成: 命中=%d, 检索=%dms, 生成=%dms, 总耗时=%dms",
            len(chunks), retrieval_time, generation_time, total_time,
        )
        return PipelineResult(
            answer=llm_result.content,
            sources=[c.to_dict() for c in chunks],
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            total_time=total_time,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            retrieved_count=len(chunks),
        )

    # ------------------------------------------------------------------
    def llm_only_chat(
        self, question: str, params: RagParams | None = None
    ) -> PipelineResult:
        """对照组: 不检索, 直接由 LLM 生成。"""
        params = params or RagParams()
        settings = get_settings()
        total_start = time.perf_counter()

        query = preprocess_query(question)
        messages = [
            LLMMessage(role="system", content=LLM_ONLY_SYSTEM_PROMPT),
            LLMMessage(role="user", content=query),
        ]
        generate_start = time.perf_counter()
        llm_result = self._get_llm().chat(
            messages=messages, temperature=params.temperature or settings.default_temperature
        )
        generation_time = int((time.perf_counter() - generate_start) * 1000)
        total_time = int((time.perf_counter() - total_start) * 1000)
        logger.info("LLM Only 问答完成: 生成=%dms, 总耗时=%dms", generation_time, total_time)
        return PipelineResult(
            answer=llm_result.content,
            sources=[],
            retrieval_time=0,
            generation_time=generation_time,
            total_time=total_time,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            retrieved_count=0,
        )
