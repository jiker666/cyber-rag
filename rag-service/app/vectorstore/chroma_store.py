"""Chroma 向量数据库封装: 每个知识库一个 Collection。"""
import logging
import threading
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.errors import RagServiceError

logger = logging.getLogger("cyber-rag.vectorstore")


@dataclass
class ChunkData:
    """待写入向量库的 Chunk 及其元数据。"""

    content: str
    document_id: int
    document_name: str
    knowledge_base_id: int
    chunk_index: int
    source: str = ""
    page: int | None = None
    metadata: dict = field(default_factory=dict)

    def full_metadata(self) -> dict:
        meta = {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "knowledge_base_id": self.knowledge_base_id,
            "chunk_index": self.chunk_index,
            "source": self.source or self.document_name,
        }
        if self.page is not None:
            meta["page"] = int(self.page)
        meta.update(self.metadata)
        return meta


def collection_name(knowledge_base_id: int) -> str:
    """知识库ID → Collection 名称(仅允许合法字符)。"""
    return f"kb_{int(knowledge_base_id)}"


class ChromaStore:
    """Chroma PersistentClient 封装。

    - 距离度量: cosine(配合 BGE 归一化向量)
    - Embedding 由外部 Provider 计算后显式传入, 保证模型可切换
    """

    def __init__(self, persist_dir: str | None = None, client=None):
        self._client = client
        self._persist_dir = persist_dir or get_settings().chroma_persist_dir
        self._lock = threading.Lock()

    @property
    def client(self):
        if self._client is None:
            import chromadb

            logger.info("初始化 Chroma 持久化客户端: %s", self._persist_dir)
            self._client = chromadb.PersistentClient(path=self._persist_dir)
        return self._client

    def _get_collection(self, knowledge_base_id: int):
        return self.client.get_or_create_collection(
            name=collection_name(knowledge_base_id),
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, knowledge_base_id: int, chunks: list[ChunkData], embeddings: list[list[float]]) -> int:
        """批量写入 Chunk。Chroma 单批上限 5461, 分批提交。"""
        if len(chunks) != len(embeddings):
            raise RagServiceError(500, "Chunk 与向量数量不一致")
        collection = self._get_collection(knowledge_base_id)
        batch_size = 1000
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            batch_embeddings = embeddings[start : start + batch_size]
            ids = [f"doc_{c.document_id}_chunk_{c.chunk_index}_{start + i}" for i, c in enumerate(batch)]
            with self._lock:
                collection.add(
                    ids=ids,
                    embeddings=batch_embeddings,
                    documents=[c.content for c in batch],
                    metadatas=[c.full_metadata() for c in batch],
                )
        logger.info(
            "知识库[%s]写入 %d 个 Chunk", knowledge_base_id, len(chunks)
        )
        return len(chunks)

    def query(
        self,
        knowledge_base_id: int,
        query_embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[dict]:
        """向量检索, 返回 [{content, metadata, score}], score 为余弦相似度。"""
        collection = self._get_collection(knowledge_base_id)
        if collection.count() == 0:
            return []
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict] = []
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]
        dists = result.get("distances") or [[]]
        for doc, meta, dist in zip(docs[0], metas[0], dists[0]):
            hits.append(
                {
                    "content": doc,
                    "metadata": meta or {},
                    # cosine distance → similarity
                    "score": round(1.0 - float(dist), 4),
                }
            )
        return hits

    def delete_by_document(self, knowledge_base_id: int, document_id: int) -> None:
        collection = self._get_collection(knowledge_base_id)
        with self._lock:
            collection.delete(where={"document_id": int(document_id)})
        logger.info("知识库[%s]删除文档[%s]全部向量", knowledge_base_id, document_id)

    def delete_collection(self, knowledge_base_id: int) -> None:
        name = collection_name(knowledge_base_id)
        try:
            self.client.delete_collection(name)
            logger.info("删除向量集合: %s", name)
        except Exception:
            logger.warning("删除向量集合失败(可能不存在): %s", name)

    def get_all(self, knowledge_base_id: int) -> list[dict]:
        """读取集合内全部文档, 供 BM25 索引构建。返回 [{content, metadata}]。"""
        collection = self._get_collection(knowledge_base_id)
        if collection.count() == 0:
            return []
        data = collection.get(include=["documents", "metadatas"])
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        return [
            {"content": doc, "metadata": meta or {}} for doc, meta in zip(docs, metas)
        ]

    def count(self, knowledge_base_id: int) -> int:
        try:
            return self._get_collection(knowledge_base_id).count()
        except Exception:
            return 0

    def document_count(self, knowledge_base_id: int) -> int:
        """集合内不同 document_id 数量。"""
        try:
            collection = self._get_collection(knowledge_base_id)
            if collection.count() == 0:
                return 0
            data = collection.get(include=["metadatas"])
            ids = {m.get("document_id") for m in (data.get("metadatas") or [])}
            return len(ids)
        except Exception:
            return 0


_store: ChromaStore | None = None
_store_lock = threading.Lock()


def get_vector_store() -> ChromaStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        _store = ChromaStore()
        return _store


def reset_vector_store() -> None:
    """测试用。"""
    global _store
    with _store_lock:
        _store = None
