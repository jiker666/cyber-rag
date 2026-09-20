"""Pipeline 自适应编排测试: 路由落地 / Trace / 置信度 / 消融开关 / 流式事件。"""
from app.llm.base import BaseLLM, LLMMessage, LLMResult
from app.rag.pipeline import ChatHistoryItem, RagParams, RagPipeline
from app.rag.reranker import BaseReranker
from app.rag.retriever import Retriever
from app.vectorstore.chroma_store import ChunkData

SQL_DOC = (
    "SQL 注入是一种将恶意 SQL 语句插入查询参数的攻击方式。防御 SQL 注入的核心是使用参数化查询和预编译语句, "
    "并对输入进行严格校验。ORM 框架默认使用参数化绑定, 能有效防止 SQL 注入。"
)


class FakeReranker(BaseReranker):
    """确定性重排: 内容含 '参数化' 者置顶(rerank_score=6.0), 其余 1.0。"""

    name = "fake-reranker"

    def rerank(self, query, chunks, top_n=3):
        ranked = sorted(
            chunks, key=lambda c: (6.0 if "参数化" in c.content else 1.0), reverse=True
        )
        for c in ranked:
            c.rerank_score = 6.0 if "参数化" in c.content else 1.0
        return ranked[:top_n]


class StreamingFakeLLM(BaseLLM):
    """流式 LLM: 3 个 delta + usage(含 TTFT)。"""

    name = "stream-fake-llm"
    model = "fake-model"

    def chat(self, messages, temperature=0.3, max_tokens=None):
        user = next((m for m in messages if m.role == "user"), None)
        return LLMResult(
            content=f"关于{user.content[:6]}的测试回答 [1]",
            prompt_tokens=80, completion_tokens=10, total_tokens=90,
        )

    def chat_stream(self, messages, temperature=0.3, max_tokens=None):
        for piece in ["第一段", "第二段", "第三段"]:
            yield {"type": "delta", "text": piece}
        yield {"type": "usage", "prompt_tokens": 80, "completion_tokens": 10,
               "ttft_ms": 500, "latency_ms": 1200}


def _ingest(store, embedding, kb_id=1, doc_id=101):
    from app.rag.chunker import chunk_text

    chunks = chunk_text(SQL_DOC, chunk_size=80, chunk_overlap=10)
    data = [
        ChunkData(
            content=c.content, document_id=doc_id, document_name="SQL注入防护指南.md",
            knowledge_base_id=kb_id, chunk_index=c.chunk_index,
            source="SQL注入防护指南.md", page=None,
        )
        for c in chunks
    ]
    store.add_chunks(kb_id, data, embedding.embed_documents([c.content for c in data]))


def _pipeline(memory_store, fake_embedding, fake_llm) -> RagPipeline:
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=FakeReranker())
    return RagPipeline(retriever=retriever, llm=fake_llm)


# ---------------- 自适应路径 ----------------
def test_adaptive_hybrid_route_with_trace(memory_store, fake_embedding, fake_llm):
    _ingest(memory_store, fake_embedding)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    result = pipeline.rag_chat(
        "如何防御 SQL 注入攻击", [1], RagParams(adaptive=True, score_threshold=0.0)
    )
    # 过程类问题 → HYBRID 路由
    assert result.route["route"] == "HYBRID"
    assert result.trace["routeReason"]
    # Trace 完整性: 阶段耗时与决策字段
    for key in ("queryAnalysisMs", "embeddingMs", "vectorSearchMs", "bm25SearchMs",
                "fusionMs", "rerankMs", "contextBuildMs", "generationMs", "totalMs",
                "route", "queryType", "rerankerUsed", "candidateCount",
                "contextTokens", "retrievalConfidence"):
        assert key in result.trace, f"trace 缺字段 {key}"
    # 置信度对象
    assert result.confidence["level"] in ("sufficient", "moderate", "insufficient")
    assert 0.0 <= result.confidence["retrievalConfidence"] <= 1.0
    # 分析对象
    assert result.analysis["queryType"] == "PROCEDURAL"
    assert result.sources


def test_adaptive_fast_route_vector_only(memory_store, fake_embedding, fake_llm, monkeypatch):
    _ingest(memory_store, fake_embedding)
    # 放宽升级阈值: Fake 向量余弦较低, 避免 FAST 因置信不足升级为 HYBRID(升级路径另有覆盖)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "fast_path_top1_min", 0.0, raising=False)
    monkeypatch.setattr(get_settings(), "fast_path_margin_min", 0.0, raising=False)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    result = pipeline.rag_chat(
        "SQL 注入的危害包括哪些", [1], RagParams(adaptive=True, score_threshold=0.0)
    )
    # 简单事实题走 FAST(vector), 无 BM25 耗时
    assert result.route["route"] == "FAST"
    assert result.route["strategy"] == "vector"
    assert result.trace["bm25SearchMs"] == 0
    # FAST 策略 skip → 不重排
    assert result.trace["rerankerUsed"] is False


def test_adaptive_fast_escalates_on_low_confidence(memory_store, fake_embedding, fake_llm):
    """FAST 路径置信不足 → 自动升级 HYBRID(trace 记录原因)"""
    _ingest(memory_store, fake_embedding)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    result = pipeline.rag_chat(
        "SQL 注入的危害包括哪些", [1], RagParams(adaptive=True, score_threshold=0.0)
    )
    # Fake 向量 top1 相似度低 → 升级为混合检索
    assert result.route["route"] == "HYBRID"
    assert result.route["strategy"] == "hybrid"
    assert "升级" in result.route["reason"]
    assert result.trace["route"] == "HYBRID"  # Trace 与最终决策同步


def test_adaptive_low_evidence_no_chunks(memory_store, fake_embedding, fake_llm):
    """无可用知识库 → 无候选 → 证据不足 + 空上下文(不强行生成编造引用)"""
    _ingest(memory_store, fake_embedding)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    result = pipeline.rag_chat("如何防御 SQL 注入攻击", [], RagParams(adaptive=True))
    assert result.sources == []
    assert result.confidence["level"] == "insufficient"
    assert result.confidence["label"] == "证据不足"
    assert result.trace["contextTokens"] == 0
    assert result.confidence["retrievalConfidence"] == 0.0


def test_non_adaptive_keeps_legacy_behavior(memory_store, fake_embedding, fake_llm):
    """传统模式: 无路由决策, 固定策略 + 固定重排开关"""
    _ingest(memory_store, fake_embedding)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    result = pipeline.rag_chat(
        "如何防御 SQL 注入攻击", [1],
        RagParams(adaptive=False, score_threshold=0.0, enable_reranker=True),
    )
    assert result.route == {}
    assert result.trace["route"] == ""
    assert result.trace["rerankerUsed"] is True  # 固定开关生效


def test_ablation_disable_rerank_gating(memory_store, fake_embedding, fake_llm):
    """消融(-Reranker Gating): 门控关闭后 enable_reranker=True → 强制重排"""
    _ingest(memory_store, fake_embedding)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    result = pipeline.rag_chat(
        "如何防御 SQL 注入攻击", [1],
        RagParams(adaptive=True, rerank_gating=False, enable_reranker=True,
                  score_threshold=0.0),
    )
    assert result.route["route"] == "HYBRID"
    assert result.trace["rerankerUsed"] is True
    assert "强制" in result.trace["rerankReason"] or "force" in result.trace["rerankReason"].lower()


def test_history_window_passed_to_llm(memory_store, fake_embedding, fake_llm):
    _ingest(memory_store, fake_embedding)
    pipeline = _pipeline(memory_store, fake_embedding, fake_llm)
    history = [
        ChatHistoryItem(role="user", content="什么是 SQL 注入"),
        ChatHistoryItem(role="assistant", content="SQL 注入是..."),
    ]
    result = pipeline.rag_chat(
        "如何防御 SQL 注入攻击", [1],
        RagParams(adaptive=True, score_threshold=0.0), history=history,
    )
    assert result.answer  # FakeLLM 正常回答
    assert fake_llm.calls, "LLM 应被调用"


# ---------------- 流式 ----------------
def test_rag_chat_stream_event_sequence(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding)
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=FakeReranker())
    pipeline = RagPipeline(retriever=retriever, llm=StreamingFakeLLM())

    events = list(pipeline.rag_chat_stream(
        "如何防御 SQL 注入攻击", [1], RagParams(adaptive=True, score_threshold=0.0)
    ))
    types = [e["type"] for e in events]
    # 事件顺序: analysis → retrieval → delta×3 → done
    assert types[0] == "analysis"
    assert types[1] == "retrieval"
    assert types.count("delta") == 3
    assert types[-1] == "done"

    analysis_evt = events[0]
    assert analysis_evt["analysis"]["queryType"] == "PROCEDURAL"
    assert analysis_evt["route"]["route"] == "HYBRID"

    retrieval_evt = events[1]
    assert retrieval_evt["sources"]
    assert "confidence" in retrieval_evt

    done = events[-1]["result"]
    assert done["answer"] == "第一段第二段第三段"
    assert done["trace"]["llmTtftMs"] == 500  # TTFT 从 LLM usage 事件透传
    assert done["sources"]
