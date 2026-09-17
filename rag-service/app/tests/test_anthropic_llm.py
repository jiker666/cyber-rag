"""Anthropic 兼容 LLM Provider 测试(离线, mock httpx)。"""
import pytest

from app.llm.anthropic_compatible import AnthropicCompatibleLLM
from app.llm.base import LLMMessage


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.text = str(payload or "")
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_anthropic_chat_text_blocks_only(monkeypatch):
    """thinking 块应被忽略, 仅拼接 text 块。"""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, body=json)
        return _FakeResponse(payload={
            "content": [
                {"type": "thinking", "thinking": "推理过程..."},
                {"type": "text", "text": "应使用参数化查询 [1]。"},
            ],
            "usage": {"input_tokens": 100, "output_tokens": 30},
        })

    monkeypatch.setattr("app.llm.anthropic_compatible.httpx.post", fake_post)
    llm = AnthropicCompatibleLLM()
    result = llm.chat(
        [
            LLMMessage(role="system", content="系统提示"),
            LLMMessage(role="user", content="如何防御SQL注入?"),
        ],
        temperature=0.3,
    )

    assert result.content == "应使用参数化查询 [1]。"
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 30
    assert result.total_tokens == 130
    # 请求结构: system 提升为顶层参数
    assert captured["url"].endswith("/v1/messages")
    assert captured["body"]["system"] == "系统提示"
    assert captured["body"]["messages"] == [{"role": "user", "content": "如何防御SQL注入?"}]
    assert "max_tokens" in captured["body"]
    # 双鉴权头
    assert "x-api-key" in captured["headers"]
    assert captured["headers"]["Authorization"].startswith("Bearer ")


def test_anthropic_error_passthrough(monkeypatch):
    from app.core.errors import LLMError

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(status_code=429, payload={"error": {"message": "余额不足"}})

    monkeypatch.setattr("app.llm.anthropic_compatible.httpx.post", fake_post)
    llm = AnthropicCompatibleLLM()
    with pytest.raises(LLMError) as exc:
        llm.chat([LLMMessage(role="user", content="hi")])
    assert "429" in str(exc.value)


def test_anthropic_requires_api_key(monkeypatch):
    from app.core.config import get_settings
    from app.core.errors import LLMError

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)
    with pytest.raises(LLMError):
        AnthropicCompatibleLLM()
