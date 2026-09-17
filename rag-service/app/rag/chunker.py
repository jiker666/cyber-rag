"""Chunk 切分: 基于 LangChain RecursiveCharacterTextSplitter, 页感知(保留 PDF 页码)。"""
import logging
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.document.cleaner import clean_text
from app.document.parser import DocumentPage

logger = logging.getLogger("cyber-rag.rag.chunker")

# 中文优先分隔符 + 英文分隔符
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", ".", "!", "?", ";", " ", ""]


@dataclass
class TextChunk:
    content: str
    page: int | None = None
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


def chunk_pages(
    pages: list[DocumentPage],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """按页切分并合并为全局有序 Chunk 列表。

    对每页单独执行 RecursiveCharacterTextSplitter, 保证跨页内容不互相污染,
    且每个 Chunk 能准确记录来源页码。
    """
    settings = get_settings()
    size = chunk_size if chunk_size is not None else settings.default_chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.default_chunk_overlap
    if size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk_overlap 必须满足 0 <= overlap < chunk_size")

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS,
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False,
        keep_separator="end",
    )

    chunks: list[TextChunk] = []
    for page in pages:
        cleaned = clean_text(page.text)
        if not cleaned:
            continue
        pieces = splitter.split_text(cleaned)
        for piece in pieces:
            if not piece.strip():
                continue
            chunks.append(TextChunk(content=piece.strip(), page=page.page))
    # 全局编号
    for idx, chunk in enumerate(chunks):
        chunk.chunk_index = idx
    logger.info("切分完成: %d 页 → %d 个 Chunk (size=%d, overlap=%d)", len(pages), len(chunks), size, overlap)
    return chunks


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """纯文本切分(无页码)。"""
    return chunk_pages([DocumentPage(text=text, page=None)], chunk_size, chunk_overlap)
