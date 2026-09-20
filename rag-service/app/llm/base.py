"""LLM Provider 抽象接口。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # system / user / assistant
    content: str


@dataclass
class LLMResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    latency_ms: int = 0


@dataclass
class BaseLLM(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResult:
        """同步对话补全。"""

    def chat_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ):
        """流式对话补全: 逐 token 产出。

        Yields:
            {"type": "delta", "text": str}                    增量文本
            {"type": "usage", "prompt_tokens": int, ...}      结束时用量(最后一个事件)
        默认未实现: 由具体 Provider 覆盖; 不支持流式时回退同步拼整段。
        """
        result = self.chat(messages, temperature, max_tokens)
        yield {"type": "delta", "text": result.content}
        yield {
            "type": "usage",
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "latency_ms": result.latency_ms,
        }
