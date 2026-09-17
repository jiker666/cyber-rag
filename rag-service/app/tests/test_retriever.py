"""Retriever 测试: 真实 Chroma 读写 + Fake Embedding。"""
from app.rag.chunker import chunk_text
from app.rag.retriever import Retriever
from app.vectorstore.chroma_store import ChunkData

SQL_DOC = (
    "SQL 注入是一种将恶意 SQL 语句插入查询参数的攻击方式。防御 SQL 注入的核心是使用参数化查询和预编译语句, "
    "并对输入进行严格校验。ORM 框架默认使用参数化绑定, 能有效防止 SQL 注入。"
)
XSS_DOC = (
    "跨站脚本攻击 XSS 是指攻击者向页面注入恶意 JavaScript 脚本。防御 XSS 的核心是对输出进行 HTML 转义, "
    "并配置 Content Security Policy 内容安全策略, 使用 HttpOnly Cookie 保护会话。"
)


def _ingest(store, embedding, kb_id, doc_id, doc_name, text):
    chunks = chunk_text(text, chunk_size=80, chunk_overlap=10)
    data = [
        ChunkData(
            content=c.content,
            document_id=doc_id,
            document_name=doc_name,
            knowledge_base_id=kb_id,
            chunk_index=c.chunk_index,
            source=doc_name,
            page=None,
        )
        for c in chunks
    ]
    vectors = embedding.embed_documents([c.content for c in data])
    store.add_chunks(kb_id, data, vectors)
    return len(data)


def test_retrieve_relevant_document(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding, 1, 101, "SQL注入防护指南.md", SQL_DOC)
    _ingest(memory_store, fake_embedding, 1, 102, "XSS防护指南.md", XSS_DOC)
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    results = retriever.retrieve(
        "如何防御 SQL 注入", knowledge_base_ids=[1], top_k=2, score_threshold=0.0
    )
    assert len(results) >= 1
    assert results[0].document_name == "SQL注入防护指南.md"
    assert results[0].score > 0


def test_threshold_filters_results(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding, 2, 201, "SQL注入防护指南.md", SQL_DOC)
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    results = retriever.retrieve(
        "如何防御 SQL 注入", knowledge_base_ids=[2], top_k=5, score_threshold=0.99
    )
    assert results == []


def test_top_k_limits(memory_store, fake_embedding):
    n = _ingest(memory_store, fake_embedding, 3, 301, "混合安全知识.txt", SQL_DOC + " " + XSS_DOC * 3)
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    results = retriever.retrieve(
        "安全", knowledge_base_ids=[3], top_k=2, score_threshold=0.0
    )
    assert len(results) <= 2
    assert n >= 2


def test_delete_by_document(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding, 4, 401, "SQL注入防护指南.md", SQL_DOC)
    assert memory_store.count(4) > 0
    memory_store.delete_by_document(4, 401)
    assert memory_store.count(4) == 0


def test_multiple_knowledge_bases(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding, 5, 501, "SQL注入防护指南.md", SQL_DOC)
    _ingest(memory_store, fake_embedding, 6, 601, "XSS防护指南.md", XSS_DOC)
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    results = retriever.retrieve(
        "XSS 攻击如何防御", knowledge_base_ids=[5, 6], top_k=5, score_threshold=0.0
    )
    assert len(results) >= 1
    assert results[0].document_name == "XSS防护指南.md"


def test_chunk_metadata_roundtrip(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding, 7, 701, "SQL注入防护指南.md", SQL_DOC)
    hits = memory_store.query(7, fake_embedding.embed_query("SQL 注入"), top_k=10)
    assert hits
    meta = hits[0]["metadata"]
    assert meta["document_id"] == 701
    assert meta["document_name"] == "SQL注入防护指南.md"
    assert meta["knowledge_base_id"] == 7
    assert meta["chunk_index"] >= 0
    assert "source" in meta
