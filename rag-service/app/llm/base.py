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
