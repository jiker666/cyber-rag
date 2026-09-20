"""OpenAI 兼容 LLM Provider: 支持 GLM / Qwen / DeepSeek / OpenAI 等接口。"""
import logging
import threading
import time

from app.core.config import get_settings
from app.core.errors import LLMError
from app.core.logging import mask_secrets
from app.llm.base import BaseLLM, LLMMessage, LLMResult

logger = logging.getLogger("cyber-rag.llm")


class OpenAICompatibleLLM(BaseLLM):
    name = "openai-compatible"

    def __init__(self):
        settings = get_settings()
        if not settings.llm_api_key:
            raise LLMError("必须通过环境变量 LLM_API_KEY 配置大模型密钥")
        self.model = settings.llm_model
        self._base_url = settings.llm_base_url
        self._timeout = settings.llm_timeout
        self._max_tokens = settings.llm_max_tokens
        self._client = None
        self._lock = threading.Lock()

    def _ensure_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    from openai import OpenAI

                    self._client = OpenAI(
                        base_url=self._base_url or None,
                        api_key=get_settings().llm_api_key,
                        timeout=self._timeout,
                    )

    def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResult:
        self._ensure_client()
        payload = [{"role": m.role, "content": m.content} for m in messages]
        logger.info(
            "LLM 请求: model=%s, messages=%d, temperature=%.2f", self.model, len(payload), temperature
        )
        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=payload,
                temperature=temperature,
                max_tokens=max_tokens or self._max_tokens,
            )
        except Exception as e:
            logger.error("LLM 调用失败: %s", mask_secrets(str(e)))
            raise LLMError(f"大模型调用失败: {mask_secrets(str(e))}") from e
        latency = int((time.perf_counter() - start) * 1000)
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        logger.info(
            "LLM 响应: %d chars, tokens=%s, latency=%dms",
            len(content),
            getattr(usage, "total_tokens", "n/a"),
            latency,
        )
        return LLMResult(
            content=content,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            model=self.model,
            latency_ms=latency,
        )

    def chat_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ):
        """SSE 流式补全(OpenAI 兼容): 逐 token yield, 记录 TTFT。"""
        self._ensure_client()
        payload = [{"role": m.role, "content": m.content} for m in messages]
        start = time.perf_counter()
        first_token_at: float | None = None
        usage = None
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=payload,
                temperature=temperature,
                max_tokens=max_tokens or self._max_tokens,
                stream=True,
                stream_options={"include_usage": True},  # 部分兼容端点不支持时自动忽略
            )
            for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    yield {"type": "delta", "text": text}
        except Exception as e:
            logger.error("LLM 流式调用失败: %s", mask_secrets(str(e)))
            raise LLMError(f"大模型流式调用失败: {mask_secrets(str(e))}") from e
        end = time.perf_counter()
        yield {
            "type": "usage",
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "ttft_ms": int((first_token_at - start) * 1000) if first_token_at else None,
            "latency_ms": int((end - start) * 1000),
        }
