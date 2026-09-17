"""BM25 与 Hybrid(RRF) 检索测试: 精确词召回是核心验收点。"""
from app.rag.bm25 import BM25Index, tokenize
from app.rag.retriever import Retriever
from app.vectorstore.chroma_store import ChunkData
from app.tests.conftest import FakeEmbedding


def _chunks(store, kb_id, docs):
    """docs: [(document_id, chunk_index, content)] 写入向量库。"""
    store.add_chunks(
        kb_id,
        [
            ChunkData(
                content=c,
                document_id=d,
                document_name=f"doc-{d}.md",
                knowledge_base_id=kb_id,
                chunk_index=i,
            )
            for d, i, c in docs
        ],
        FakeEmbedding().embed_documents([c for _, _, c in docs]),
    )


# ---------------------------------------------------------------- tokenize

def test_tokenize_ascii_terms_kept():
    assert tokenize("CWE-918 SSRF") == ["cwe-918", "ssrf"]


def test_tokenize_cjk_bigram():
    assert tokenize("注入") == ["注入"]
    assert tokenize("SQL注入攻击") == ["sql", "注入", "入攻", "攻击"]


# ---------------------------------------------------------------- BM25Index

def test_bm25_exact_term_outranks_similar():
    """查询 CWE-918 时, 含精确词条的文档应排在只含 CWE-89 的文档前。"""
    index = BM25Index([
        {"key": "a", "content": "CWE-89 SQL 注入: 用户输入拼接查询导致的漏洞"},
        {"key": "b", "content": "CWE-918 SSRF 服务端请求伪造: 内网地址校验缺失"},
        {"key": "c", "content": "跨站脚本 XSS 的防御方案"},
    ])
    hits = index.search("CWE-918", top_n=3)
    assert hits and hits[0][0] == "b"


def test_bm25_no_match_returns_empty():
    index = BM25Index([{"key": "a", "content": "注入攻击"}])
    assert index.search("quantum chromodynamics", top_n=3) == []


# ---------------------------------------------------------------- Hybrid Retriever

def test_hybrid_recalls_exact_id_vector_misses(memory_store, fake_embedding):
    """向量检索对精确 ID 召回不佳时, BM25 应把它拉回 Top 结果。"""
    _chunks(
        memory_store,
        1,
        [
            (1, 0, "CWE-89 SQL 注入漏洞原理与参数化查询防御"),
            (2, 0, "CWE-918 SSRF 服务端请求伪造原理与白名单校验"),
        ],
    )
    from app.rag.bm25 import reset_bm25_store

    reset_bm25_store()
    retriever = Retriever(store=memory_store, embedding=fake_embedding)

    # 纯向量: FakeEmbedding 词袋相似度, 查询与 doc1(注入) 共享更多字符
    vec_hits = retriever.retrieve(
        "CWE-918 是什么", knowledge_base_ids=[1], top_k=1, score_threshold=0.0
    )
    # 混合: BM25 精确命中 cwe-918 应把 doc2 顶到第一
    hyb_hits = retriever.retrieve(
        "CWE-918 是什么",
        knowledge_base_ids=[1],
        top_k=2,
        score_threshold=0.0,
        retrieval_strategy="hybrid",
    )
    assert hyb_hits, "混合检索应至少召回 BM25 精确命中"
    assert hyb_hits[0].document_id == 2
    # BM25 独有命中的余弦分允许为 None
    assert all(c.score is None or c.score >= 0.0 for c in hyb_hits)


def test_hybrid_respects_threshold(memory_store, fake_embedding):
    """阈值过高时向量候选清空, 但 BM25 仍可召回(精确词优先于阈值拒答)。"""
    _chunks(
        memory_store,
        1,
        [(1, 0, "JWT 令牌签名校验缺失风险"), (2, 0, "CORS 跨域配置错误风险")],
    )
    from app.rag.bm25 import reset_bm25_store

    reset_bm25_store()
    retriever = Retriever(store=memory_store, embedding=fake_embedding)

    hits = retriever.retrieve(
        "CORS 配置", knowledge_base_ids=[1], top_k=2, score_threshold=0.99,
        retrieval_strategy="hybrid",
    )
    assert hits and hits[0].document_id == 2
    assert hits[0].score is None  # 仅 BM25 命中
