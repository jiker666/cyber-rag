"""Cache 层: Query Embedding LRU + Version-Aware Retrieval Cache。

失效逻辑不依赖 TTL:
- EmbeddingCache: key=(normalized_query, model), LRU 淘汰; 同一问题重复提问不重算向量。
- RetrievalCache: key 含 kb_version, 知识库任何变更(新增/删除文档、重建索引、重新向量化)
  使 kb_version 自增, 旧 key 永不匹配 → 自动失效, 不会返回过期结果。
kb_version 持久化在向量库目录(kb_versions.json), 进程重启不丢。
"""
import json
import logging
import re
import threading
from collections import OrderedDict
from pathlib import Path

from app.core.config import get_settings
from app.vectorstore.chroma_store import ChromaStore, get_vector_store

logger = logging.getLogger("cyber-rag.rag.caches")


def normalize_query(query: str) -> str:
    """缓存 key 用的查询归一: 小写 + 去全部空白。"""
    return re.sub(r"\s+", "", (query or "")).lower()[:500]


class LRUCache:
    """线程安全 LRU(带命中率统计)。"""

    def __init__(self, maxsize: int):
        self._maxsize = max(1, maxsize)
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return None

    def put(self, key, value) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "hitRate": self.hit_rate, "size": len(self._data)}


class EmbeddingCache:
    """查询向量 LRU 缓存。key=(normalized_query, embedding_model)。"""

    def __init__(self, maxsize: int):
        self._cache = LRUCache(maxsize)

    def get(self, query: str, model: str) -> list[float] | None:
        return self._cache.get((normalize_query(query), model))

    def put(self, query: str, model: str, embedding: list[float]) -> None:
        self._cache.put((normalize_query(query), model), embedding)

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> dict:
        return {"embeddingCache": self._cache.stats()}


class KBVersionRegistry:
    """知识库版本注册表: 任何向量集合变更 version+1; 持久化到向量库目录。"""

    def __init__(self, persist_dir: str | None = None):
        self._persist_dir = Path(persist_dir or get_settings().chroma_persist_dir)
        self._file = self._persist_dir / "kb_versions.json"
        self._versions: dict[int, int] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if self._file.exists():
                raw = json.loads(self._file.read_text(encoding="utf-8"))
                self._versions = {int(k): int(v) for k, v in raw.items()}
        except Exception:
            logger.warning("kb_versions.json 读取失败, 从空版本开始(缓存将全量重建)")
            self._versions = {}

    def _save(self) -> None:
        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps({str(k): v for k, v in self._versions.items()}), encoding="utf-8"
            )
        except Exception:
            logger.exception("kb_versions.json 写入失败")

    def version(self, kb_id: int) -> int:
        with self._lock:
            return self._versions.get(int(kb_id), 1)

    def bump(self, kb_id: int) -> int:
        with self._lock:
            nxt = self._versions.get(int(kb_id), 1) + 1
            self._versions[int(kb_id)] = nxt
            self._save()
            logger.info("知识库[%s]版本自增 → v%s(检索缓存自动失效)", kb_id, nxt)
            return nxt

    def versions(self, kb_ids: list[int]) -> tuple[int, ...]:
        return tuple(self.version(k) for k in sorted(int(x) for x in kb_ids))


class RetrievalCache:
    """版本感知检索缓存。

    key=(kb_ids, kb_versions, normalized_query, strategy, top_k, entity_boost,
         reranker_model, embedding_model, small_to_large)
    缓存值为"融合后候选"(重排不在缓存内: 门控与 CrossEncoder 每次真实执行,
    保证 rerank activation 统计与排序行为一致)。
    知识库变更 → version 变化 → key 不匹配 → 自然失效(LRU 容量兜底内存)。
    """

    def __init__(self, maxsize: int):
        self._cache = LRUCache(maxsize)

    @staticmethod
    def build_key(
        kb_ids: list[int],
        versions: tuple[int, ...],
        query: str,
        strategy: str,
        top_k: int,
        entity_boost: bool,
        small_to_large: bool,
    ) -> tuple:
        settings = get_settings()
        return (
            tuple(sorted(int(k) for k in kb_ids)),
            versions,
            normalize_query(query),
            strategy,
            int(top_k),
            bool(entity_boost),
            settings.reranker_model,
            settings.embedding_model,
            bool(small_to_large),
        )

    def get(self, key: tuple):
        return self._cache.get(key)

    def put(self, key: tuple, value) -> None:
        self._cache.put(key, value)

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> dict:
        return {"retrievalCache": self._cache.stats()}


# ---------------------------------------------------------------- 全局单例
_embedding_cache: EmbeddingCache | None = None
_retrieval_cache: RetrievalCache | None = None
_version_registry: KBVersionRegistry | None = None
_singleton_lock = threading.Lock()


def get_embedding_cache() -> EmbeddingCache:
    global _embedding_cache
    if _embedding_cache is None:
        with _singleton_lock:
            if _embedding_cache is None:
                _embedding_cache = EmbeddingCache(get_settings().embedding_cache_size)
    return _embedding_cache


def get_retrieval_cache() -> RetrievalCache:
    global _retrieval_cache
    if _retrieval_cache is None:
        with _singleton_lock:
            if _retrieval_cache is None:
                _retrieval_cache = RetrievalCache(get_settings().retrieval_cache_size)
    return _retrieval_cache


def get_kb_version_registry(store: ChromaStore | None = None) -> KBVersionRegistry:
    """全局版本注册表; 可传入向量库(测试隔离用)。"""
    global _version_registry
    if _version_registry is None:
        with _singleton_lock:
            if _version_registry is None:
                _version_registry = KBVersionRegistry(
                    (store or get_vector_store())._persist_dir
                )
    return _version_registry


def bump_kb_version(kb_id: int) -> None:
    """向量集合变更钩子: 入库/删除/重建后调用。"""
    get_kb_version_registry().bump(kb_id)


def cache_stats() -> dict:
    stats = {}
    stats.update(get_embedding_cache().stats())
    stats.update(get_retrieval_cache().stats())
    return stats


def reset_caches() -> None:
    """测试用。"""
    global _embedding_cache, _retrieval_cache, _version_registry
    with _singleton_lock:
        if _embedding_cache is not None:
            _embedding_cache.clear()
        if _retrieval_cache is not None:
            _retrieval_cache.clear()
        _embedding_cache = None
        _retrieval_cache = None
        _version_registry = None
