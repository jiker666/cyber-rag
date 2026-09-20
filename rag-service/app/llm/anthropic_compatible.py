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
        stop_reason = data.get("stop_reason")
        # GLM 5.x thinking 与正文共享 max_tokens 预算: stop_reason=max_tokens 时可能正文为空(推理耗尽预算)
        if not content:
            logger.warning(
                "LLM 返回空正文: stop_reason=%s, output_tokens=%d, max_tokens=%d "
                "(thinking 可能耗尽输出预算, 建议调大 LLM_MAX_TOKENS)",
                stop_reason, completion_tokens, body["max_tokens"],
            )
        logger.info(
            "LLM 响应: %d chars, tokens=%d, latency=%dms, stop_reason=%s",
            len(content), prompt_tokens + completion_tokens, latency, stop_reason,
        )
        return LLMResult(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=self.model,
            latency_ms=latency,
        )

    def chat_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ):
        """SSE 流式补全: 逐 token yield, 记录 TTFT(首 token 时延)。

        GLM 5.x thinking 块会以 content_block_delta(thinking_delta) 下发,
        仅透传 text_delta, 与非流式路径口径一致。
        """
        import json as _json

        system_parts = [m.content for m in messages if m.role == "system"]
        chat_msgs = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        body: dict = {
            "model": self.model,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature,
            "messages": chat_msgs,
            "stream": True,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        headers = {
            "x-api-key": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "anthropic-version": _ANTHROPIC_VERSION,
            "accept": "text/event-stream",
        }
        start = time.perf_counter()
        first_token_at: float | None = None
        prompt_tokens = 0
        completion_tokens = 0
        text_chars = 0
        stop_reason = None
        try:
            with httpx.stream(
                "POST", f"{self._base_url}/v1/messages",
                headers=headers, json=body, timeout=self._timeout,
            ) as resp:
                if resp.status_code != 200:
                    detail = mask_secrets(resp.read()[:300].decode("utf-8", "ignore"))
                    raise LLMError(f"大模型流式调用失败: HTTP {resp.status_code} {detail}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        event = _json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    etype = event.get("type")
                    if etype == "message_start":
                        usage = (event.get("message") or {}).get("usage") or {}
                        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
                    elif etype == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            if first_token_at is None:
                                first_token_at = time.perf_counter()
                            text_chars += len(delta["text"])
                            yield {"type": "delta", "text": delta["text"]}
                    elif etype == "message_delta":
                        usage = event.get("usage") or {}
                        completion_tokens = int(usage.get("output_tokens", 0) or 0)
                        stop_reason = (event.get("delta") or {}).get("stop_reason")
        except LLMError:
            raise
        except Exception as e:
            logger.error("LLM 流式调用异常: %s", mask_secrets(str(e)))
            raise LLMError(f"大模型流式调用失败: {mask_secrets(str(e))}") from e
        end = time.perf_counter()
        if text_chars == 0:
            logger.warning(
                "LLM 流式零正文: stop_reason=%s, output_tokens=%d, max_tokens=%d "
                "(thinking 可能耗尽输出预算, 建议调大 LLM_MAX_TOKENS)",
                stop_reason, completion_tokens, body["max_tokens"],
            )
        yield {
            "type": "usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "ttft_ms": int((first_token_at - start) * 1000) if first_token_at else None,
            "latency_ms": int((end - start) * 1000),
        }
