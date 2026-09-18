"""Embedding 工厂: provider 取值别名与回退行为。"""
import pytest

import app.embedding.factory as factory
from app.embedding.local_bge import LocalBGEEmbedding
from app.embedding.openai_compatible import OpenAICompatibleEmbedding


@pytest.fixture(autouse=True)
def _reset_provider():
    factory.reset_embedding_provider()
    yield
    factory.reset_embedding_provider()


def test_openai_compatible_alias(monkeypatch):
    """'openai-compatible' 是 docker-compose 早期使用的取值, 必须映射到远程 Provider,
    否则会静默落入本地分支并尝试下载名为 text-embedding-3-small 的本地模型。"""
    settings = factory.get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "openai-compatible", raising=False)
    monkeypatch.setattr(settings, "embedding_api_key", "sk-test", raising=False)
    provider = factory.get_embedding_provider()
    assert isinstance(provider, OpenAICompatibleEmbedding)


def test_openai_provider(monkeypatch):
    settings = factory.get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "embedding_api_key", "sk-test", raising=False)
    assert isinstance(factory.get_embedding_provider(), OpenAICompatibleEmbedding)


def test_local_fallback(monkeypatch):
    settings = factory.get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "local", raising=False)
    provider = factory.get_embedding_provider()
    assert isinstance(provider, LocalBGEEmbedding)
    # 本地 Provider 懒加载, 不应在构造时触发模型下载
    assert provider._model is None
