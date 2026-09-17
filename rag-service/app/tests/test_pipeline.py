"""RAG Pipeline 测试: Fake LLM + Fake Retriever。"""
from app.rag.pipeline import ChatHistoryItem, RagParams, RagPipeline
from app.rag.retriever import RetrievedChunk


class StubRetriever:
    """固定返回预置片段的检索器。"""

    def __init__(self, chunks):
        self.chunks = chunks
        self.queries = []

    def retrieve(self, query, knowledge_base_ids, **kwargs):
        self.queries.append(query)
        return self.chunks


def _chunk(doc_name="Java安全开发规范.pdf", page=21, score=0.85):
    return RetrievedChunk(
        content="Spring Boot 中防止 SQL 注入应使用参数化查询, 例如 JdbcTemplate 的 ? 占位符。",
        document_id=1,
        document_name=doc_name,
        knowledge_base_id=1,
        chunk_index=0,
        source=doc_name,
        page=page,
        score=score,
    )


def test_rag_chat_returns_answer_and_sources(fake_llm):
    retriever = StubRetriever([_chunk()])
    pipeline = RagPipeline(retriever=retriever, llm=fake_llm)
    result = pipeline.rag_chat("Spring Boot 如何防止 SQL 注入?", [1])
    assert "测试回答" in result.answer
    assert len(result.sources) == 1
    assert result.sources[0]["documentName"] == "Java安全开发规范.pdf"
    assert result.sources[0]["page"] == 21
    assert result.sources[0]["score"] == 0.85
    assert result.retrieval_time >= 0
    assert result.generation_time >= 0
    assert result.total_time >= result.retrieval_time


def test_rag_chat_preprocesses_query(fake_llm):
    retriever = StubRetriever([])
    pipeline = RagPipeline(retriever=retriever, llm=fake_llm)
    pipeline.rag_chat("   什么是  XSS?   ", [1])
    assert retriever.queries[0] == "什么是 XSS?"


def test_rag_chat_with_history(fake_llm):
    retriever = StubRetriever([_chunk()])
    pipeline = RagPipeline(retriever=retriever, llm=fake_llm)
    history = [ChatHistoryItem(role="user", content="SQL 注入的原理是什么?"),
               ChatHistoryItem(role="assistant", content="SQL 注入是...")]
    pipeline.rag_chat("那如何防御?", [1], history=history)
    # system + 2 history + 1 user = 4 条消息
    assert len(fake_llm.calls[-1]) == 4


def test_llm_only_chat_has_no_sources(fake_llm):
    pipeline = RagPipeline(retriever=None, llm=fake_llm)
    result = pipeline.llm_only_chat("什么是 CSRF?")
    assert result.answer
    assert result.sources == []
    assert result.retrieval_time == 0
    assert result.retrieved_count == 0


def test_empty_question_rejected(fake_llm):
    import pytest

    pipeline = RagPipeline(retriever=StubRetriever([]), llm=fake_llm)
    with pytest.raises(Exception):
        pipeline.rag_chat("   ", [1])


def test_rag_prompt_contains_context_and_citation(fake_llm):
    retriever = StubRetriever([_chunk()])
    pipeline = RagPipeline(retriever=retriever, llm=fake_llm)
    pipeline.rag_chat("如何防止 SQL 注入?", [1])
    last_user = [m for m in fake_llm.calls[-1] if m.role == "user"][-1]
    assert "知识库片段" in last_user.content
    assert "[1] 来源: Java安全开发规范.pdf" in last_user.content
    assert "第 21 页" in last_user.content


def test_no_knowledge_scene_prompt_declares_no_evidence(fake_llm):
    """无知识场景: 检索为空时, Prompt 必须显式注入'未检索到'声明, 引导 LLM 拒答而非编造。"""
    retriever = StubRetriever([])  # 无任何命中
    pipeline = RagPipeline(retriever=retriever, llm=fake_llm)
    result = pipeline.rag_chat("量子色动力学中的夸克禁闭是什么?", [1])
    assert result.sources == []  # 无来源 → 前端不显示引用, 不伪装 RAG 答案
    user_prompt = fake_llm.calls[-1][-1].content
    assert "知识库中未检索到相关内容" in user_prompt
    # 系统提示包含无依据拒答规则
    system_prompt = fake_llm.calls[-1][0].content
    assert "未找到充分依据" in system_prompt
