"""Anthropic Messages 协议 LLM Provider。

支持智谱 BigModel(https://open.bigmodel.cn/api/anthropic)等 Anthropic 兼容接口。
注意: GLM 5.x 系列会返回 thinking 推理块, 仅拼接 type=text 的内容块作为回答。
"""
import logging
import time

import httpx

from app.core.config import get_settings
from app.core.errors import LLMError
from app.core.logging import mask_secrets
from app.llm.base import BaseLLM, LLMMessage, LLMResult

logger = logging.getLogger("cyber-rag.llm")

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicCompatibleLLM(BaseLLM):
    name = "anthropic-compatible"

    def __init__(self):
        settings = get_settings()
        if not settings.llm_api_key:
            raise LLMError("必须通过环境变量 LLM_API_KEY 配置大模型密钥")
        self.model = settings.llm_model
        self._base_url = (settings.llm_base_url or "https://api.anthropic.com").rstrip("/")
        self._api_key = settings.llm_api_key
        self._timeout = settings.llm_timeout
        self._max_tokens = settings.llm_max_tokens

    def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResult:
        # Anthropic 协议: system 为顶层参数, messages 只含 user/assistant
        system_parts = [m.content for m in messages if m.role == "system"]
        chat_msgs = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        body: dict = {
            "model": self.model,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature,
            "messages": chat_msgs,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        # 同时携带两种鉴权头, 兼容 x-api-key 与 Bearer Token 两种接入方式
        headers = {
            "x-api-key": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        logger.info(
            "LLM 请求(anthropic): model=%s, messages=%d, temperature=%.2f",
            self.model, len(chat_msgs), temperature,
        )
        start = time.perf_counter()
        try:
            resp = httpx.post(
                f"{self._base_url}/v1/messages",
                headers=headers,
                json=body,
                timeout=self._timeout,
            )
            if resp.status_code != 200:
                detail = mask_secrets(resp.text[:300])
                logger.error("LLM 调用失败: HTTP %d %s", resp.status_code, detail)
                raise LLMError(f"大模型调用失败: HTTP {resp.status_code} {detail}")
            data = resp.json()
        except LLMError:
            raise
        except Exception as e:
            logger.error("LLM 调用异常: %s", mask_secrets(str(e)))
            raise LLMError(f"大模型调用失败: {mask_secrets(str(e))}") from e
        latency = int((time.perf_counter() - start) * 1000)

        # 仅拼接文本块; 忽略 thinking 等非文本块
        content = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
        completion_tokens = int(usage.get("output_tokens", 0) or 0)
        logger.info(
            "LLM 响应: %d chars, tokens=%d, latency=%dms",
            len(content), prompt_tokens + completion_tokens, latency,
        )
        return LLMResult(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=self.model,
            latency_ms=latency,
        )
