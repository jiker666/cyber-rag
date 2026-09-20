"""API 集成测试: TestClient + 全链路 Mock(离线)。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(monkeypatch, fake_embedding, fake_llm, memory_store):
    from app.rag.pipeline import RagPipeline as RealPipeline
    from app.rag.retriever import RetrievedChunk, Retriever as RealRetriever

    chunk = RetrievedChunk(
        content="使用参数化查询防止 SQL 注入。",
        document_id=101, document_name="SQL注入防护指南.md", knowledge_base_id=1,
        chunk_index=0, source="SQL注入防护指南.md", page=3, score=0.88,
    )

    class StubRetriever(RealRetriever):
        def __init__(self, *a, **kw):
            pass

        def retrieve(self, query, knowledge_base_ids, **kw):
            return [chunk]

    class StubPipeline(RealPipeline):
        def __init__(self, *a, **kw):
            super().__init__(retriever=StubRetriever(), llm=fake_llm)

    # 替换路由内的构造入口
    monkeypatch.setattr("app.api.routes.RagPipeline", StubPipeline)
    monkeypatch.setattr("app.api.routes.Retriever", StubRetriever)
    monkeypatch.setattr("app.api.routes.get_vector_store", lambda: memory_store)
    monkeypatch.setattr("app.api.ingest_service.get_embedding_provider", lambda: fake_embedding)
    monkeypatch.setattr("app.api.ingest_service.get_vector_store", lambda: memory_store)

    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "UP"


def test_ingest_text_and_chat(client):
    # 1. 文本入库(真实执行: 清洗→切片→Fake向量化→真实Chroma写入)
    resp = client.post(
        "/api/ingest/text",
        json={
            "knowledge_base_id": 1,
            "document_id": 101,
            "document_name": "SQL注入防护指南.md",
            "source": "SQL注入防护指南.md",
            "text": "SQL 注入防御: 使用参数化查询与预编译语句。" * 10,
            "chunk_size": 100,
            "chunk_overlap": 20,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunkCount"] >= 1

    # 2. RAG 问答(Stub 检索 + Fake LLM)
    resp = client.post(
        "/api/chat/query",
        json={"question": "如何防御 SQL 注入?", "knowledge_base_ids": [1], "top_k": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "[1]" in data["answer"]
    assert data["sources"][0]["documentName"] == "SQL注入防护指南.md"
    assert data["sources"][0]["page"] == 3
    assert "retrievalTime" in data and "generationTime" in data

    # 3. 入库统计与删除
    resp = client.get("/api/ingest/stats/1")
    assert resp.status_code == 200
    resp = client.delete("/api/ingest/document/1/101")
    assert resp.status_code == 200


def test_llm_only(client):
    resp = client.post("/api/chat/llm-only", json={"question": "什么是 CSRF?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"] == []
    assert data["answer"]


def test_chat_query_accepts_java_camelcase(client):
    """Java 后端以 camelCase 序列化 ChatRequest, 必须被别名正确解析。"""
    resp = client.post(
        "/api/chat/query",
        json={
            "question": "如何防御 SQL 注入?",
            "knowledgeBaseIds": [1],
            "topK": 3,
            "scoreThreshold": 0.1,
            "enableReranker": False,
            "rerankTopN": 3,
            "historyWindow": 4,
            "history": [{"role": "user", "content": "你好"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrievedCount"] >= 1
    assert data["sources"][0]["documentName"] == "SQL注入防护指南.md"


def test_file_upload_rejects_bad_extension(client, tmp_path):
    import io

    resp = client.post(
        "/api/ingest/file",
        files={"file": ("evil.jsp", io.BytesIO(b"<%out.print(1);%>"), "application/octet-stream")},
        data={"knowledge_base_id": "1", "document_id": "1"},
    )
    assert resp.status_code == 422


def test_file_upload_txt(client, tmp_path):
    import io

    resp = client.post(
        "/api/ingest/file",
        files={"file": ("notes.txt", io.BytesIO("XSS 防御核心是输出转义。".encode()), "text/plain")},
        data={"knowledge_base_id": "9", "document_id": "901", "chunk_size": "60", "chunk_overlap": "10"},
    )
    assert resp.status_code == 200
    assert resp.json()["chunkCount"] >= 1


def test_retrieval_search(client):
    resp = client.post(
        "/api/retrieval/search",
        json={"question": "SQL 注入", "knowledge_base_ids": [1], "top_k": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["chunks"][0]["documentName"] == "SQL注入防护指南.md"


def test_evaluation_batch(client):
    resp = client.post(
        "/api/evaluation/batch",
        json={
            "mode": "RAG_LLM",
            "knowledgeBaseId": 1,
            "params": {"topK": 3, "scoreThreshold": 0.1},
            "items": [
                {
                    "itemId": 1,
                    "question": "如何防御 SQL 注入?",
                    "expectedKeywords": "参数化查询",
                    "expectedSource": "SQL注入防护指南",
                },
                {"itemId": 2, "question": "什么是 XSS?", "expectedKeywords": "转义"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2
    r0 = data["results"][0]
    assert r0["retrievalHit"] is True
    assert r0["citationMatched"] == 1.0
    m = data["metrics"]
    assert m["completed"] == 2
    assert m["retrievalHitRate"] == 1.0
    assert m["citationValidity"] == 1.0


def test_evaluation_batch_llm_only_retrieval_metrics_not_applicable(client):
    """LLM_ONLY 无检索: Hit/P@K/R@K/MRR 应为 null(不适用), 不落 0.0。"""
    resp = client.post(
        "/api/evaluation/batch",
        json={
            "mode": "LLM_ONLY",
            "items": [
                {
                    "itemId": 1,
                    "question": "如何防御 SQL 注入?",
                    "expectedKeywords": "参数化查询",
                    "expectedSource": "SQL注入防护指南",
                }
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    r0 = data["results"][0]
    assert r0["retrievalHit"] is None
    assert r0["precisionAtK"] is None
    assert r0["recallAtK"] is None
    assert r0["mrr"] is None
    assert r0["citationMatched"] is None
    assert data["metrics"]["retrievalHitRate"] is None
    assert data["metrics"]["precisionAtK"] is None


def test_validation_error_format(client):
    resp = client.post("/api/chat/query", json={"question": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 422


def test_internal_token_required(monkeypatch, fake_embedding, fake_llm):
    from app.core.config import get_settings

    # 阻断真实 Provider 构建, /api/config 在测试内保持离线
    monkeypatch.setattr("app.api.routes.get_embedding_provider", lambda: fake_embedding)
    monkeypatch.setattr("app.api.routes.get_llm_provider", lambda: fake_llm)
    get_settings().rag_internal_token = "secret-token"
    try:
        with TestClient(app) as c:
            resp = c.get("/api/config")
            assert resp.status_code == 401
            resp = c.get("/api/config", headers={"X-Internal-Token": "secret-token"})
            assert resp.status_code == 200
            assert "apiKey" not in str(resp.json())
    finally:
        get_settings().rag_internal_token = ""


# ---------------- SSE 流式问答 ----------------
def test_chat_stream_sse_events(client):
    import json

    resp = client.post(
        "/api/chat/stream",
        json={"question": "如何防御 SQL 注入", "knowledgeBaseIds": [1]},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = [
        json.loads(line[len("data: "):])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    types = [e["type"] for e in events]
    assert types[0] == "analysis"
    assert types[1] == "retrieval"
    assert "delta" in types
    assert types[-1] == "done"
    done = events[-1]["result"]
    assert done["answer"]
    assert "trace" in done and "route" in done and "confidence" in done
    assert done["sources"][0]["documentName"] == "SQL注入防护指南.md"


def test_chat_query_returns_adaptive_fields(client):
    resp = client.post(
        "/api/chat/query",
        json={"question": "如何防御 SQL 注入", "knowledgeBaseIds": [1], "adaptive": False},
    )
    assert resp.status_code == 200
    data = resp.json()["data"] if "data" in resp.json() else resp.json()
    # 响应结构兼容旧字段 + 新增 trace/analysis/confidence
    for key in ("answer", "sources", "trace", "analysis", "confidence"):
        assert key in data


def test_config_endpoint_includes_adaptive_and_caches(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "adaptive" in data
    assert data["adaptive"]["thresholds"]["rerankConfidence"] > 0
    assert "caches" in data
