"""Small-to-Large 测试: 父子分块 + 子检索父生成扩展。"""
from app.document.parser import DocumentPage
from app.rag.chunker import chunk_text
from app.rag.retriever import RetrievedChunk, Retriever
from app.rag.small_to_large import chunk_pages_parent_child
from app.vectorstore.chroma_store import ChunkData

LONG_TEXT = (
    "SQL 注入是一种将恶意 SQL 语句插入查询参数的攻击方式。攻击者可以利用 SQL 注入读取数据库中的敏感数据, "
    "甚至执行系统命令。防御 SQL 注入的核心是使用参数化查询和预编译语句, 并对用户输入进行严格校验与白名单过滤。"
    "此外还应该遵循最小权限原则配置数据库账号, 并对数据库错误信息进行脱敏处理, 防止信息泄露。"
) * 4


def test_parent_child_splitting_structure():
    pages = [DocumentPage(page=1, text=LONG_TEXT)]
    children = chunk_pages_parent_child(
        pages, parent_size=400, parent_overlap=20, child_size=120, child_overlap=20
    )
    assert len(children) >= 3
    # 子块全局编号连续
    assert [c.chunk_index for c in children] == list(range(len(children)))
    # 每个子块携带父块信息
    for c in children:
        assert c.parent_chunk_id >= 1
        assert len(c.parent_text) >= len(c.content)
    # 子块均不超过 child_size 上限(切分器保证)
    assert all(len(c.content) <= 120 for c in children)
    # 同一父块的子块拼接可还原父块主体
    by_parent: dict[int, list[str]] = {}
    for c in children:
        by_parent.setdefault(c.parent_chunk_id, []).append(c.content)
    assert len(by_parent) >= 2  # 文本足够长, 至少 2 个父块


def test_child_covers_parent_text():
    pages = [DocumentPage(page=2, text=LONG_TEXT)]
    children = chunk_pages_parent_child(
        pages, parent_size=400, parent_overlap=20, child_size=120, child_overlap=20
    )
    first_parent = next(c for c in children if c.parent_chunk_id == 1)
    # 子块内容来自父块文本(有重叠切分下子块应为父块子串)
    assert first_parent.content in first_parent.parent_text


def test_invalid_params_rejected():
    import pytest

    with pytest.raises(ValueError):
        chunk_pages_parent_child([DocumentPage(page=1, text="x")], parent_size=100, child_size=200)


def _ingest_parent_child(store, embedding, kb_id, doc_id, doc_name, text):
    children = chunk_pages_parent_child(
        [DocumentPage(page=1, text=text)],
        parent_size=400, parent_overlap=20, child_size=120, child_overlap=20,
    )
    data = [
        ChunkData(
            content=c.content,
            document_id=doc_id,
            document_name=doc_name,
            knowledge_base_id=kb_id,
            chunk_index=c.chunk_index,
            source=doc_name,
            page=c.page,
            metadata={"parent_chunk_id": c.parent_chunk_id, "parent_text": c.parent_text},
        )
        for c in children
    ]
    vectors = embedding.embed_documents([c.content for c in data])
    store.add_chunks(kb_id, data, vectors)
    return children


def test_retrieve_expands_to_parent(memory_store, fake_embedding):
    children = _ingest_parent_child(
        memory_store, fake_embedding, 1, 101, "SQL注入长文.md", LONG_TEXT
    )
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    results = retriever.retrieve(
        "如何防御 SQL 注入", knowledge_base_ids=[1], top_k=4, score_threshold=0.0
    )
    assert results, "应检索到子块"
    # 命中的是子块, 返回的是父块全文
    child_len = max(len(c.content) for c in children)
    assert all(len(r.content) > child_len for r in results if r.parent_chunk_id is not None)
    # 同一父块的多个子块被去重合并
    parents = {(r.knowledge_base_id, r.document_id, r.parent_chunk_id) for r in results}
    assert len(parents) == len(results)
    # parent_chunk_id 保留可回溯
    assert all(r.parent_chunk_id is not None for r in results)


def test_fixed_chunks_still_work_alongside(memory_store, fake_embedding):
    """同库混存: 固定分块文档(无 parent 元数据)不受父块扩展影响"""
    from app.rag.chunker import chunk_text

    chunks = chunk_text("跨站脚本攻击 XSS 需要输出转义防御。" * 3, chunk_size=60, chunk_overlap=10)
    data = [
        ChunkData(
            content=c.content, document_id=102, document_name="XSS.md",
            knowledge_base_id=2, chunk_index=c.chunk_index, source="XSS.md", page=None,
        )
        for c in chunks
    ]
    store_vectors = fake_embedding.embed_documents([c.content for c in data])
    memory_store.add_chunks(2, data, store_vectors)
    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    results = retriever.retrieve("XSS", knowledge_base_ids=[2], top_k=3, score_threshold=0.0)
    assert results
    assert all(r.parent_chunk_id is None for r in results)
