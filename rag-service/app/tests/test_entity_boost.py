"""Security Entity Boost 测试: CVE 等精确编号的确定性优先。"""
from app.rag.adaptive import decide_route
from app.rag.analyzer import analyze_query
from app.rag.retriever import Retriever, RetrievedChunk, RetrievalMeta
from app.vectorstore.chroma_store import ChunkData

CVE_DOC = (
    "CVE-2021-44228 是 Apache Log4j2 中的远程代码执行漏洞, CVSS 评分 10.0, "
    "攻击者通过 JNDI 注入即可控制服务器, 影响范围极广, 被称为 Log4Shell。"
)
CONCEPT_DOC = (
    "远程代码执行漏洞是指攻击者能够在目标服务器上执行任意代码的漏洞类型, "
    "常见于反序列化、模板注入与表达式注入等场景, 危害极大需要优先修复。"
)


def _ingest(store, embedding, kb_id, doc_id, doc_name, text):
    from app.rag.chunker import chunk_text

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
    data = [
        ChunkData(
            content=c.content, document_id=doc_id, document_name=doc_name,
            knowledge_base_id=kb_id, chunk_index=c.chunk_index, source=doc_name, page=None,
        )
        for c in chunks
    ]
    vectors = embedding.embed_documents([c.content for c in data])
    store.add_chunks(kb_id, data, vectors)


def _chunk(content, name, doc_id):
    return RetrievedChunk(
        content=content, document_id=doc_id, document_name=name, knowledge_base_id=1,
        chunk_index=0, source=name, page=1, score=0.8,
    )


# ---------------- 融合层: 确定性加权反转 ----------------
def test_fuse_entity_boost_inverts_ranking():
    """无编号文档双路排名第 1(更高 RRF), 含 CVE 编号文档排名第 2;
    实体加权 +0.03 后含编号文档反超 → 编号精确匹配优先"""
    vec = [_chunk(CONCEPT_DOC, "概念.md", 1), _chunk(CVE_DOC, "CVE通告.md", 2)]
    bm25 = [_chunk(CONCEPT_DOC, "概念.md", 1), _chunk(CVE_DOC, "CVE通告.md", 2)]

    no_boost, _ = Retriever._fuse(vec, bm25, [], apply_entity_boost=False)
    assert no_boost[0].document_name == "概念.md"
    assert no_boost[0].rrf_score > no_boost[1].rrf_score

    boosted, _ = Retriever._fuse(vec, bm25, ["CVE-2021-44228"], apply_entity_boost=True)
    assert boosted[0].document_name == "CVE通告.md"
    assert boosted[0].entity_matched is True
    assert boosted[0].rrf_score > boosted[1].rrf_score


def test_fuse_boost_only_with_identifiers():
    # 每次融合用新对象(RetrievedChunk 可变, 避免跨调用状态残留)
    chunks, _ = Retriever._fuse(
        [_chunk(CVE_DOC, "CVE通告.md", 2)], [], ["CVE-2021-44228"], apply_entity_boost=True
    )
    assert chunks[0].entity_matched is True
    # 无精确编号 → 不加权
    chunks2, _ = Retriever._fuse(
        [_chunk(CVE_DOC, "CVE通告.md", 2)], [], [], apply_entity_boost=True
    )
    assert chunks2[0].entity_matched is False


# ---------------- 检索层: EXACT 路由端到端 ----------------
def test_exact_route_prioritizes_cve_document(memory_store, fake_embedding):
    _ingest(memory_store, fake_embedding, 1, 11, "概念.md", CONCEPT_DOC)
    _ingest(memory_store, fake_embedding, 1, 12, "CVE通告.md", CVE_DOC)

    query = "CVE-2021-44228 漏洞的原理"
    analysis = analyze_query(query)
    decision = decide_route(analysis)
    assert decision.route == "EXACT"  # 前置: 该问句应走实体路由

    retriever = Retriever(store=memory_store, embedding=fake_embedding, reranker=None)
    meta = RetrievalMeta()
    results = retriever.retrieve(
        query, knowledge_base_ids=[1], score_threshold=0.0,
        analysis=analysis, decision=decision, entity_boost=True, meta=meta,
    )
    assert results, "应检索到候选"
    assert meta.entity_boosted is True
    # 含编号文档在 Top-K 中, 且排在不含编号文档之前
    names = [r.document_name for r in results]
    assert "CVE通告.md" in names
    if "概念.md" in names:
        assert names.index("CVE通告.md") < names.index("概念.md")
    top_cve = next(r for r in results if r.document_name == "CVE通告.md")
    assert top_cve.entity_matched is True
