"""Small-to-Large Retrieval 的索引侧: Parent-Child 分块。

索引结构:
  Parent Chunk (默认 1024 字符, overlap 100)
    ├── Child 1 (默认 320 字符, overlap 60)
    ├── Child 2
    └── Child 3 ...

- 向量化与检索用 Child(小块精确); 送入 LLM 用 Parent(上下文完整)。
- 每个入库的 Child 携带元数据: parent_chunk_id + parent_text(父块全文),
  检索命中后由 Retriever._expand_to_parents 去重并替换为父块内容。
- 引用仍对应原文档: document_name/page 保留自命中的子块, parent_chunk_id 可回溯。
"""
import logging
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.document.cleaner import clean_text
from app.document.parser import DocumentPage
from app.rag.chunker import _SEPARATORS, TextChunk

logger = logging.getLogger("cyber-rag.rag.small_to_large")


@dataclass
class ChildChunk(TextChunk):
    """子块: 检索单元, 携带父块信息。"""

    parent_chunk_id: int = 0
    parent_text: str = ""
    document_id: int = 0
    document_name: str = ""
    knowledge_base_id: int = 0
    source: str = ""
    metadata: dict = field(default_factory=dict)


def chunk_pages_parent_child(
    pages: list[DocumentPage],
    parent_size: int | None = None,
    parent_overlap: int | None = None,
    child_size: int | None = None,
    child_overlap: int | None = None,
) -> list[ChildChunk]:
    """两级切分: 先 Parent(大块)后 Child(小块), 全部 Child 全局编号。

    chunk_index 为子块全局序号; parent_chunk_id 为父块序号(独立编号)。
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    settings = get_settings()
    p_size = parent_size or settings.parent_chunk_size
    p_overlap = parent_overlap if parent_overlap is not None else 100
    c_size = child_size or settings.child_chunk_size
    c_overlap = child_overlap if child_overlap is not None else settings.child_chunk_overlap
    if p_size <= 0 or c_size <= 0 or c_size > p_size:
        raise ValueError("parent/child chunk 参数非法(需 0 < child_size ≤ parent_size)")

    parent_splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS, chunk_size=p_size, chunk_overlap=p_overlap,
        length_function=len, is_separator_regex=False, keep_separator="end",
    )
    child_splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS, chunk_size=c_size, chunk_overlap=c_overlap,
        length_function=len, is_separator_regex=False, keep_separator="end",
    )

    children: list[ChildChunk] = []
    parent_id = 0
    for page in pages:
        cleaned = clean_text(page.text)
        if not cleaned:
            continue
        for parent_text in parent_splitter.split_text(cleaned):
            if not parent_text.strip():
                continue
            parent_id += 1
            for piece in child_splitter.split_text(parent_text):
                if not piece.strip():
                    continue
                children.append(
                    ChildChunk(content=piece.strip(), page=page.page,
                               parent_chunk_id=parent_id, parent_text=parent_text.strip())
                )
    for idx, child in enumerate(children):
        child.chunk_index = idx
    logger.info(
        "Parent-Child 切分: %d 页 → %d 父块 → %d 子块 (parent=%d, child=%d/%d)",
        len(pages), parent_id, len(children), p_size, c_size, c_overlap,
    )
    return children
