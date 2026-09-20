"""Cache 层测试: LRU 淘汰 / 查询归一 / 版本失效 / key 构成。"""
import pytest

from app.rag.caches import (
    EmbeddingCache,
    KBVersionRegistry,
    LRUCache,
    RetrievalCache,
    normalize_query,
    reset_caches,
)


def setup_function(_):
    reset_caches()


def teardown_function(_):
    reset_caches()


# ---------------- 查询归一 ----------------
def test_normalize_query():
    assert normalize_query("  如何 防御SQL 注入 ") == "如何防御sql注入"
    assert normalize_query("ABC") == "abc"
    assert normalize_query("") == ""


# ---------------- LRU ----------------
def test_lru_basic_get_put():
    c = LRUCache(maxsize=2)
    assert c.get("a") is None
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.get("b") is None


def test_lru_eviction_order():
    c = LRUCache(maxsize=2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")  # a 变为最近使用
    c.put("c", 3)  # 淘汰 b
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_lru_stats_and_hit_rate():
    c = LRUCache(maxsize=4)
    c.put("a", 1)
    c.get("a")  # hit
    c.get("x")  # miss
    s = c.stats()
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["hitRate"] == 0.5
    assert s["size"] == 1


# ---------------- EmbeddingCache ----------------
def test_embedding_cache_key_includes_model():
    c = EmbeddingCache(maxsize=8)
    c.put("如何防御 SQL 注入", "bge-small", [0.1, 0.2])
    assert c.get("如何防御SQL注入", "bge-small") == [0.1, 0.2]  # 归一后命中
    assert c.get("如何防御 SQL 注入", "other-model") is None  # 模型不同不串


# ---------------- KBVersionRegistry ----------------
def test_version_registry_bump_and_persist(tmp_path):
    reg = KBVersionRegistry(persist_dir=str(tmp_path))
    assert reg.version(1) == 1
    assert reg.bump(1) == 2
    assert reg.bump(1) == 3
    # 持久化: 新实例从文件恢复
    reg2 = KBVersionRegistry(persist_dir=str(tmp_path))
    assert reg2.version(1) == 3
    assert reg2.version(99) == 1  # 未见过的 KB 默认 v1


def test_version_registry_versions_sorted_tuple(tmp_path):
    reg = KBVersionRegistry(persist_dir=str(tmp_path))
    reg.bump(5)
    assert reg.versions([3, 5, 7]) == (1, 2, 1)


# ---------------- RetrievalCache key ----------------
def test_retrieval_cache_key_changes_on_version():
    k1 = RetrievalCache.build_key([1, 2], (1, 1), "如何防御", "hybrid", 5, True, False)
    k2 = RetrievalCache.build_key([1, 2], (1, 2), "如何防御", "hybrid", 5, True, False)
    assert k1 != k2  # KB 版本变化 → key 变化 → 旧缓存自然失效


def test_retrieval_cache_key_changes_on_query_normalization():
    k1 = RetrievalCache.build_key([1], (1,), "如何 防御", "hybrid", 5, True, False)
    k2 = RetrievalCache.build_key([1], (1,), "如何防御", "hybrid", 5, True, False)
    assert k1 == k2  # 等价写法共享缓存


def test_retrieval_cache_key_changes_on_strategy_and_k():
    base = RetrievalCache.build_key([1], (1,), "q", "hybrid", 5, True, False)
    assert base != RetrievalCache.build_key([1], (1,), "q", "vector", 5, True, False)
    assert base != RetrievalCache.build_key([1], (1,), "q", "hybrid", 8, True, False)
    assert base != RetrievalCache.build_key([1], (1,), "q", "hybrid", 5, False, False)


def test_retrieval_cache_put_get_roundtrip():
    c = RetrievalCache(maxsize=4)
    key = c.build_key([1], (1,), "q", "hybrid", 5, True, False)
    assert c.get(key) is None
    c.put(key, ([1, 2, 3], "meta"))
    assert c.get(key) == ([1, 2, 3], "meta")
