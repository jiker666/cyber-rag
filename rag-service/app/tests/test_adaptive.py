"""Adaptive Routing / Reranker Gating / Evidence Confidence 测试(边界值)。"""
import pytest

from app.rag.adaptive import (
    CONFIDENCE_LABELS,
    decide_route,
    retrieval_confidence,
    RetrievalSignals,
    should_rerank,
)
from app.rag.analyzer import analyze_query
from app.core.config import get_settings


def _analysis(q: str):
    return analyze_query(q)


# ---------------- 路由 ----------------
def test_route_exact_for_cve():
    d = decide_route(_analysis("CVE-2021-44228 漏洞原理"))
    assert d.route == "EXACT"
    assert d.strategy == "hybrid"
    assert d.rerank_policy == "auto"


def test_route_fast_for_simple_factual():
    d = decide_route(_analysis("HTTPS 默认端口是多少"))
    assert d.route == "FAST"
    assert d.strategy == "vector"
    assert d.top_k == 3
    assert d.rerank_policy == "skip"


def test_route_hybrid_for_procedural():
    d = decide_route(_analysis("如何防御 SQL 注入攻击"))
    assert d.route == "HYBRID"


def test_route_hybrid_force_for_comparative():
    d = decide_route(_analysis("SQL注入和XSS的区别是什么"))
    assert d.route == "HYBRID"
    assert d.rerank_policy == "force"


def test_route_decompose_gated_by_complexity(monkeypatch):
    settings = get_settings()
    # 阈值调到 10: 多跳问题也达不到 → 不分解(严格门控验证)
    monkeypatch.setattr(settings, "complexity_threshold", 10.0, raising=False)
    d = decide_route(_analysis("常见的Web漏洞有哪些以及如何检测"))
    assert d.route == "HYBRID"
    assert d.need_decompose is False


def test_route_decompose_when_complexity_passes(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "complexity_threshold", 5.0, raising=False)
    d = decide_route(_analysis("常见的Web漏洞有哪些以及如何检测"))
    assert d.route == "DECOMPOSE"
    assert d.need_decompose is True
    assert d.rerank_policy == "force"


# ---------------- 门控 ----------------
def _signals(top1=None, top2=None, margin=None, agreement=None, count=10):
    return RetrievalSignals(
        top1_score=top1, top2_score=top2, score_margin=margin,
        agreement=agreement, candidate_count=count,
    )


def test_gate_skip_policy_wins():
    d = decide_route(_analysis("HTTPS 默认端口是多少"))
    use, reason = should_rerank(d, _analysis("HTTPS 默认端口是多少"), _signals(count=10))
    assert use is False
    assert "FAST" in reason


def test_gate_force_policy_wins():
    a = decide_route(_analysis("SQL注入和XSS的区别是什么"))
    use, _ = should_rerank(a, _analysis("SQL注入和XSS的区别是什么"), _signals(count=10))
    assert use is True


def test_gate_few_candidates_skips():
    a = _analysis("如何防御 SQL 注入攻击")
    d = decide_route(a)
    use, reason = should_rerank(d, a, _signals(count=3))
    assert use is False
    assert "候选" in reason


def test_gate_high_confidence_skips():
    """top1 高 + margin 大 + 双路一致 → 不重排(核心降本路径)"""
    a = _analysis("如何防御 SQL 注入攻击")
    d = decide_route(a)
    use, _ = should_rerank(
        d, a, _signals(top1=0.9, top2=0.5, margin=0.4, agreement=0.8, count=10)
    )
    assert use is False


def test_gate_small_margin_reranks():
    a = _analysis("如何防御 SQL 注入攻击")
    d = decide_route(a)
    use, reason = should_rerank(
        d, a, _signals(top1=0.9, top2=0.88, margin=0.02, agreement=0.8, count=10)
    )
    assert use is True
    assert "分差小" in reason


def test_gate_low_top1_reranks():
    a = _analysis("如何防御 SQL 注入攻击")
    d = decide_route(a)
    use, reason = should_rerank(
        d, a, _signals(top1=0.3, top2=0.1, margin=0.2, agreement=0.8, count=10)
    )
    assert use is True
    assert "相似度不足" in reason


def test_gate_agreement_low_still_skips_when_strong():
    """agreement 低但 top1/margin 极强: 规则 4 要求三者同时满足才跳过;
    agreement 不满足 → 落入后续规则。margin/margin 分差大 + top1 高 → 默认不重排"""
    a = _analysis("如何防御 SQL 注入攻击")
    d = decide_route(a)
    use, _ = should_rerank(
        d, a, _signals(top1=0.9, top2=0.5, margin=0.4, agreement=0.1, count=10)
    )
    assert use is False  # 无低置信信号触发, 落入默认不重排


# ---------------- 证据置信度 ----------------
def test_confidence_zero_candidates():
    conf, level = retrieval_confidence(RetrievalSignals(candidate_count=0), 5)
    assert conf == 0.0
    assert level == "insufficient"


def test_confidence_sufficient_formula():
    """手算对拍: top1=0.9, agreement=0.8, margin=0.15+, count=K
    conf = 0.55*0.9 + 0.20*0.8 + 0.15*1 + 0.10*1 = 0.905"""
    signals = RetrievalSignals(top1_score=0.9, score_margin=0.15, agreement=0.8, candidate_count=5)
    conf, level = retrieval_confidence(signals, 5)
    assert conf == 0.905
    assert level == "sufficient"


def test_confidence_moderate():
    signals = RetrievalSignals(top1_score=0.5, score_margin=0.05, agreement=0.4, candidate_count=3)
    conf, level = retrieval_confidence(signals, 5)
    assert 0.40 <= conf < 0.65
    assert level == "moderate"


def test_confidence_rerank_blends_sigmoid():
    """已重排: top1 信号 = 0.5×余弦 + 0.5×sigmoid(logit)"""
    signals = RetrievalSignals(
        top1_score=0.8, score_margin=0.2, agreement=0.8, candidate_count=5, rerank_top1=4.0
    )
    import math

    blended = 0.5 * 0.8 + 0.5 * (1 / (1 + math.exp(-4.0)))
    expected = 0.55 * blended + 0.20 * 0.8 + 0.15 * 1.0 + 0.10 * 1.0
    conf, _ = retrieval_confidence(signals, 5)
    assert abs(conf - round(expected, 4)) < 1e-6


def test_confidence_labels_complete():
    assert CONFIDENCE_LABELS == {
        "sufficient": "证据充分", "moderate": "证据一般", "insufficient": "证据不足",
    }
