"""Dynamic Context Optimizer 测试: token 估算 / 去重 / 相邻合并 / 预算。"""
from app.rag.analyzer import analyze_query
from app.rag.context_optimizer import (
    budget_chunk_count,
    estimate_tokens,
    optimize_context,
)
from app.rag.retriever import RetrievedChunk
from app.core.config import get_settings


def _chunk(content, doc=1, idx=0, kb=1, score=0.9):
    return RetrievedChunk(
        content=content, document_id=doc, document_name=f"doc{doc}.md",
        knowledge_base_id=kb, chunk_index=idx, source=f"doc{doc}.md", page=1,
        score=score,
    )


def test_estimate_tokens_cjk_and_ascii():
    # 4 汉字 ≈ 3, 4 ASCII ≈ 1.12 → int(3 + 1.12) = 4
    assert estimate_tokens("注入攻击abcd") == 4
    assert estimate_tokens("") == 0


def test_budget_chunk_count_scales_with_complexity():
    settings = get_settings()
    low = budget_chunk_count(1.5, settings)
    high = budget_chunk_count(9.0, settings)
    assert low < high
    assert settings.min_context_chunks <= low
    assert high <= settings.max_context_chunks


def test_near_duplicate_removed():
    text = "使用参数化查询和预编译语句防止 SQL 注入攻击, 对输入进行严格校验"
    chunks = [_chunk(text, idx=0, score=0.9), _chunk(text + "。", idx=1, score=0.85)]
    sel = optimize_context(chunks, analyze_query("如何防御SQL注入"))
    assert sel.dropped_duplicates == 1
    assert len(sel.chunks) == 1
    assert sel.chunks[0].content == text  # 保留高分块


def test_adjacent_chunks_merged():
    c0 = _chunk("第一段内容。" * 5, idx=0, score=0.9)
    c1 = _chunk("第二段内容。" * 5, idx=1, score=0.85)
    sel = optimize_context([c0, c1], analyze_query("如何防御SQL注入"))
    assert sel.merged_adjacent == 1
    assert len(sel.chunks) == 1
    assert "第一段内容" in sel.chunks[0].content and "第二段内容" in sel.chunks[0].content


def test_non_adjacent_not_merged():
    c0 = _chunk("段落A。" * 10, idx=0, score=0.9)
    c2 = _chunk("段落B。" * 10, idx=2, score=0.85)  # idx 跳跃
    sel = optimize_context([c0, c2], analyze_query("如何防御SQL注入"))
    assert sel.merged_adjacent == 0
    assert len(sel.chunks) == 2


def test_chunk_budget_truncates():
    # 主题互异的 6 块(近重复删除不触发), 简单问题预算 2~3 块
    topics = ["账户安全", "密码策略", "网络隔离", "日志审计", "应急响应", "漏洞管理"]
    chunks = [
        _chunk(f"{t}主题的详细说明与操作要点。{t}相关内容补充。" * 6, idx=i * 2, score=0.9 - i * 0.01)
        for i, t in enumerate(topics)
    ]
    sel = optimize_context(chunks, analyze_query("HTTPS 默认端口是多少"))
    assert len(sel.chunks) <= 3
    assert sel.dropped_by_budget >= 1
    # 相关性排序保持: 保留的是前面的高分块
    assert sel.chunks[0].chunk_index == 0


def test_token_budget_truncates():
    # 每块约 2456 tokens; 预算 5000 → 收 2 块(4912)后第 3 块超预算截断
    topics = ["账户安全", "密码策略", "网络隔离", "日志审计", "应急响应", "漏洞管理"]
    chunks = [
        _chunk(f"{t}主题的详细说明与操作要点。" * 200, idx=i * 2, score=0.9 - i * 0.01)
        for i, t in enumerate(topics)
    ]
    sel = optimize_context(chunks, analyze_query("如何防御SQL注入"), token_budget=5000)
    assert sel.context_tokens <= 5000
    assert len(sel.chunks) == 2
    assert sel.dropped_by_budget == 4


def test_empty_input():
    sel = optimize_context([], analyze_query("任意"))
    assert sel.chunks == []
    assert sel.context_tokens == 0


def test_complex_query_gets_larger_budget():
    simple = analyze_query("HTTPS 默认端口是多少")
    complex_q = analyze_query("常见的Web漏洞有哪些以及如何检测")
    settings = get_settings()
    assert budget_chunk_count(complex_q.complexity, settings) >= budget_chunk_count(
        simple.complexity, settings
    )
