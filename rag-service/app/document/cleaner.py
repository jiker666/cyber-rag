"""文本清洗: 去除控制字符/冗余空白/页眉页脚噪声, 保留正文语义。"""
import re
import unicodedata

# 连续 3 个以上相同字符的装饰线, 如 ---- ==== ****
_DECORATION_RE = re.compile(r"^\s*([-=_*#~·—–]{3,})\s*$", re.M)
# 纯页码行
_PAGE_NUMBER_RE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$", re.M)
# 连续空白(含全角空格)压缩为一个
_WHITESPACE_RE = re.compile(r"[ \t　\x0b\f\r]+")


def clean_text(text: str) -> str:
    """应用全部清洗规则。"""
    if not text:
        return ""
    # 1. 去除不可见控制字符(保留换行与制表符, 制表符由第 4 步统一压缩)
    text = "".join(ch for ch in text if ch in ("\n", "\t") or unicodedata.category(ch) != "Cc")
    # 2. Unicode 规范化
    text = unicodedata.normalize("NFKC", text)
    # 3. 去除装饰线与纯页码行
    text = _DECORATION_RE.sub("", text)
    text = _PAGE_NUMBER_RE.sub("", text)
    # 4. 行内连续空白压缩
    text = _WHITESPACE_RE.sub(" ", text)
    # 5. 连续空行压缩
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
