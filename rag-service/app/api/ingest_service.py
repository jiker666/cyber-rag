"""文档入库服务: 解析 → 清洗 → 切片 → 向量化 → 写入 Chroma。"""
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import DocumentParseError, RagServiceError
from app.document.cleaner import clean_text
from app.document.parser import DocumentPage, parse_document, validate_file
from app.embedding.factory import get_embedding_provider
from app.rag.chunker import TextChunk, chunk_pages
from app.vectorstore.chroma_store import ChunkData, get_vector_store

logger = logging.getLogger("cyber-rag.ingest")


def _chunks_to_store_chunks(
    chunks: list[TextChunk],
    document_id: int,
    document_name: str,
    knowledge_base_id: int,
    source: str,
) -> list[ChunkData]:
    store_chunks: list[ChunkData] = []
    for c in chunks:
        metadata: dict = {}
        # Parent-Child 模式: 子块携带父块编号与全文(小到大检索依据)
        parent_id = getattr(c, "parent_chunk_id", None)
        parent_text = getattr(c, "parent_text", None)
        if parent_id is not None:
            metadata["parent_chunk_id"] = int(parent_id)
        if parent_text:
            metadata["parent_text"] = str(parent_text)
        store_chunks.append(
            ChunkData(
                content=c.content,
                document_id=document_id,
                document_name=document_name,
                knowledge_base_id=knowledge_base_id,
                chunk_index=c.chunk_index,
                source=source or document_name,
                page=c.page,
                metadata=metadata,
            )
        )
    return store_chunks


def ingest_file(
    file_path: str | Path,
    filename: str,
    knowledge_base_id: int,
    document_id: int,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    chunk_mode: str = "fixed",
) -> dict:
    """文件入库全流程, 返回 {chunk_count, char_count}。

    chunk_mode: fixed(固定分块) | parent_child(父子分块, 小块检索大块生成)
    """
    settings = get_settings()
    size = Path(file_path).stat().st_size
    validate_file(filename, size, settings.max_file_size_mb)
    logger.info("开始入库: kb=%s, doc=%s, file=%s, mode=%s", knowledge_base_id, document_id, filename, chunk_mode)
    pages = parse_document(file_path, filename)
    return _ingest_pages(
        pages, filename, knowledge_base_id, document_id, filename,
        chunk_size, chunk_overlap, chunk_mode,
    )


def ingest_text(
    text: str,
    document_name: str,
    source: str,
    knowledge_base_id: int,
    document_id: int,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    chunk_mode: str = "fixed",
) -> dict:
    """纯文本入库(接口层直接传入文本)。"""
    if not text or not text.strip():
        raise DocumentParseError("文本内容为空")
    pages = [DocumentPage(text=clean_text(text), page=None)]
    return _ingest_pages(
        pages, document_name, knowledge_base_id, document_id, source,
        chunk_size, chunk_overlap, chunk_mode,
    )


def _ingest_pages(
    pages: list[DocumentPage],
    document_name: str,
    knowledge_base_id: int,
    document_id: int,
    source: str,
    chunk_size: int | None,
    chunk_overlap: int | None,
    chunk_mode: str = "fixed",
) -> dict:
    # 切片(固定分块或父子分块; chunk_size 参数在父子模式下映射为父块大小)
    if chunk_mode == "parent_child":
        from app.rag.small_to_large import chunk_pages_parent_child

        chunks: list[TextChunk] = chunk_pages_parent_child(pages, parent_size=chunk_size)
    else:
        chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise DocumentParseError("清洗与切分后无有效内容")
    char_count = sum(len(c.content) for c in chunks)

    # 向量化(Embedding Provider 可切换)
    embedding = get_embedding_provider()
    texts = [c.content for c in chunks]
    vectors = embedding.embed_documents(texts)

    # 写入向量库
    store_chunks = _chunks_to_store_chunks(
        chunks, document_id, document_name, knowledge_base_id, source
    )
    store = get_vector_store()
    store.delete_by_document(knowledge_base_id, document_id)  # 重新入库前清理旧向量
    store.add_chunks(knowledge_base_id, store_chunks, vectors)
    # 知识库变更 → 版本自增, 检索缓存自动失效
    from app.rag.caches import bump_kb_version

    bump_kb_version(knowledge_base_id)
    logger.info(
        "入库完成: kb=%s, doc=%s(%s), mode=%s, chunks=%d, chars=%d",
        knowledge_base_id, document_id, document_name, chunk_mode, len(chunks), char_count,
    )
    return {"chunk_count": len(chunks), "char_count": char_count}
