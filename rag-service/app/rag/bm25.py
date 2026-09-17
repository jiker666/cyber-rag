"""轻量 BM25: 解决安全领域精确词(CWE-918/CVE-xxxx/缩写)的召回问题。

- 分词: ASCII 词元(含连字符, 保留 CWE-918 形态) + CJK 二元组, 无外部依赖
- 索引按知识库懒构建并缓存, 依据集合条目数变化自动失效重建
"""
import logging
import math
import re
import threading
from collections import Counter

from app.vectorstore.chroma_store import ChromaStore

logger = logging.getLogger("cyber-rag.rag.bm25")

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
_CJK_RUN_RE = re.compile(r"[一-鿿]+")


def tokenize(text: str) -> list[str]:
    """ASCII 词元(小写化) + CJK 二元组(单字原样保留)。"""
    tokens = [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]
    for run in _CJK_RUN_RE.findall(text or ""):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


class BM25Index:
    """Okapi BM25(k1=1.5, b=0.75), 文档集为知识库全部 Chunk。"""

    def __init__(self, docs: list[dict]):
        # docs: [{key, content}], key 唯一标识一个 chunk
        self._k1 = 1.5
        self._b = 0.75
        self._doc_keys: list = []
        self._doc_len: list[int] = []
        self._tf: list[Counter] = []
        df: Counter = Counter()
        for doc in docs:
            toks = tokenize(doc["content"])
            counter = Counter(toks)
            self._doc_keys.append(doc["key"])
            self._doc_len.append(len(toks) or 1)
            self._tf.append(counter)
            for term in counter:
                df[term] += 1
        n = len(docs) or 1
        self._avgdl = sum(self._doc_len) / n
        self._idf = {
            t: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for t, d in df.items()
        }

    def search(self, query: str, top_n: int) -> list[tuple[str, float]]:
        """返回 [(key, score)] 按相关性降序。"""
        q_terms = set(tokenize(query))
        if not q_terms:
            return []
        scores: list[tuple[float, int]] = []
        for i, tf in enumerate(self._tf):
            s = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = tf[term] * (self._k1 + 1)
                norm = tf[term] + self._k1 * (1 - self._b + self._b * self._doc_len[i] / self._avgdl)
                s += idf * denom / norm
            scores.append((s, i))
        scores.sort(reverse=True)
        return [
            (self._doc_keys[i], s) for s, i in scores[:top_n] if s > 0
        ]


class BM25Store:
    """按知识库缓存 BM25 索引, 集合条目数变化时自动重建。"""

    def __init__(self, store: ChromaStore):
        self._store = store
        self._indexes: dict[int, tuple[int, BM25Index, dict]] = {}
        self._lock = threading.Lock()

    def _index_for(self, kb_id: int) -> tuple[BM25Index, dict] | None:
        docs = self._store.get_all(int(kb_id))
        if not docs:
            return None
        cached = self._indexes.get(int(kb_id))
        if cached and cached[0] == len(docs):
            return cached[1], cached[2]
        index = BM25Index([{"key": (d["metadata"].get("document_id"), d["metadata"].get("chunk_index")), "content": d["content"]} for d in docs])
        meta_map = {
            (d["metadata"].get("document_id"), d["metadata"].get("chunk_index")): d
            for d in docs
        }
        with self._lock:
            self._indexes[int(kb_id)] = (len(docs), index, meta_map)
        return index, meta_map

    def search(self, kb_id: int, query: str, top_n: int) -> list[dict]:
        """返回 [{content, metadata, score(BM25)}] 按 BM25 分降序。"""
        built = self._index_for(kb_id)
        if not built:
            return []
        index, meta_map = built
        hits = []
        for key, score in index.search(query, top_n):
            doc = meta_map.get(key)
            if doc:
                hits.append(
                    {"content": doc["content"], "metadata": doc["metadata"], "score": round(score, 4)}
                )
        return hits


_bm25_store: BM25Store | None = None
_bm25_lock = threading.Lock()


def get_bm25_store(store: ChromaStore | None = None) -> BM25Store:
    """获取全局 BM25 索引器; 可传入自定义向量库(测试/多实例场景)。"""
    global _bm25_store
    if _bm25_store is not None and store is None:
        return _bm25_store
    with _bm25_lock:
        if _bm25_store is None or store is not None:
            from app.vectorstore.chroma_store import get_vector_store

            _bm25_store = BM25Store(store or get_vector_store())
        return _bm25_store


def reset_bm25_store() -> None:
    """测试用。"""
    global _bm25_store
    with _bm25_lock:
        _bm25_store = None
