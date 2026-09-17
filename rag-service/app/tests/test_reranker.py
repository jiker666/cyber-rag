

def test_get_reranker_request_level_override(monkeypatch):
    """请求级 enableReranker=True 必须覆盖全局 RAG_RERANKER_ENABLED=False。

    回归: 曾因工厂只读全局配置, 返回 NoopReranker 导致重排实验静默失效。
    """
    from app.rag.reranker import CrossEncoderReranker, NoopReranker, get_reranker
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "reranker_enabled", False)

    # 全局禁用 -> 默认 Noop
    assert isinstance(get_reranker(), NoopReranker)
    # 请求级启用 -> 必须 CrossEncoder, 不受全局配置影响
    assert isinstance(get_reranker(enabled=True), CrossEncoderReranker)
    # 请求级禁用 -> Noop
    assert isinstance(get_reranker(enabled=False), NoopReranker)
