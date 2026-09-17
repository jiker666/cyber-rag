"""LLM Provider 工厂单例。"""
import logging
import threading

from app.core.config import get_settings
from app.llm.anthropic_compatible import AnthropicCompatibleLLM
from app.llm.base import BaseLLM
from app.llm.openai_compatible import OpenAICompatibleLLM

logger = logging.getLogger("cyber-rag.llm.factory")

_llm: BaseLLM | None = None
_lock = threading.Lock()


def get_llm_provider() -> BaseLLM:
    global _llm
    if _llm is not None:
        return _llm
    with _lock:
        if _llm is not None:
            return _llm
        settings = get_settings()
        provider = settings.llm_provider.lower()
        if provider == "anthropic":
            logger.info(
                "初始化 LLM Provider: provider=anthropic-compatible, model=%s, base_url=%s(已隐藏密钥)",
                settings.llm_model,
                settings.llm_base_url,
            )
            _llm = AnthropicCompatibleLLM()
        else:
            logger.info(
                "初始化 LLM Provider: provider=openai-compatible, model=%s, base_url=%s(已隐藏密钥)",
                settings.llm_model,
                settings.llm_base_url,
            )
            _llm = OpenAICompatibleLLM()
        return _llm


def reset_llm_provider() -> None:
    """测试用: 重置单例。"""
    global _llm
    with _lock:
        _llm = None
