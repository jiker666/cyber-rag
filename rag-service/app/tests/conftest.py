"""测试夹具: Fake Embedding / Fake LLM / 内存 Chroma, 全部离线可运行。"""
import hashlib
import math

import chromadb
import pytest

from app.embedding.base import BaseEmbedding
from app.llm.base import BaseLLM, LLMMessage, LLMResult
from app.vectorstore.chroma_store import ChromaStore, reset_vector_store


class FakeEmbedding(BaseEmbedding):
    """确定性伪向量: 词袋哈希叠加, 共享词越多余弦相似度越高。"""

    name = "fake"
    dimension = 64

    @staticmethod
    def _vec(text: str) -> list[float]:
        vec = [0.0] * 64
        tokens = list(text)  # 中文字符级
        for tok in tokens:
            if tok.strip():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % 64] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 6) for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FakeLLM(BaseLLM):
    """离线 LLM: RAG 模式输出带 [1] 引用的回答, 便于断言引用链路。"""

    name = "fake-llm"
    model = "fake-model"

    def __init__(self):
        self.calls: list[list[LLMMessage]] = []

    def chat(self, messages, temperature=0.3, max_tokens=None) -> LLMResult:
        self.calls.append(messages)
        user = next((m for m in reversed(messages) if m.role == "user"), None)
        content = user.content if user else ""
        if "知识库片段" in content and "[" in content:
            answer = "[1] 根据知识库内容生成的测试回答。"
        else:
            answer = "这是 LLM Only 模式的通用回答, 不包含知识库引用。"
        return LLMResult(content=answer, prompt_tokens=100, completion_tokens=20, total_tokens=120)


@pytest.fixture(autouse=True)
def _offline_providers(monkeypatch):
    """全局兜底: 任何测试路径都不得构建真实 Embedding/LLM(防模型下载)。"""
    import app.embedding.factory as emb_factory
    import app.llm.factory as llm_factory
    from app.core.config import get_settings

    monkeypatch.setattr(emb_factory, "_provider", FakeEmbedding())
    monkeypatch.setattr(llm_factory, "_llm", FakeLLM())
    # 测试与本地 .env 解耦: 清空内部令牌, 由 test_internal_token_required 自行设置
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_internal_token", "", raising=False)


@pytest.fixture()
def fake_embedding():
    return FakeEmbedding()


@pytest.fixture()
def fake_llm():
    return FakeLLM()


@pytest.fixture()
def memory_store(tmp_path):
    """临时目录持久化的 Chroma(真实读写, 测试后自动清理)。"""
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    store = ChromaStore(persist_dir=str(tmp_path / "chroma"), client=client)
    reset_vector_store()
    yield store
    reset_vector_store()
