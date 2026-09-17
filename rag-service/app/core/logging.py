"""日志配置: 统一格式, 禁止输出 API Key 等敏感信息。"""
import logging
import re
import sys

_SENSITIVE_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),          # OpenAI 风格 Key
    re.compile(r"(Bearer\s+[A-Za-z0-9._\-]{8,})"),   # Bearer Token
    re.compile(r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?[^'\"\s,}]+)", re.I),
]
_MASK = "***MASKED***"


def mask_secrets(text: str) -> str:
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub(_MASK, text)
    return text


class SensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            try:
                record.args = tuple(
                    mask_secrets(a) if isinstance(a, str) else a for a in record.args
                )
            except Exception:
                pass
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        return True


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:  # 避免重复初始化
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(SensitiveFilter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    # chroma / sentence_transformers 日志降级
    for noisy in ("chromadb", "sentence_transformers", "httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


logger = logging.getLogger("cyber-rag")
