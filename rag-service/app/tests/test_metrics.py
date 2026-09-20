"""评价指标测试。"""
from app.evaluation.metrics import (
    aggregate,
    citation_validity,
    has_fabricated_citation,
    keyword_hit_rate,
    mrr,
    retrieval_metrics,
)


def _source(doc_name="SQL注入防护指南.md"):
    return {"documentName": doc_name, "source": doc_name, "content": "..."}


def test_keyword_hit_rate():
    answer = "防御 SQL 注入应使用参数化查询与预编译语句"
    rate = keyword_hit_rate(answer, "SQL注入,参数化查询,输入校验")
    assert rate == pytest_approx(2 / 3)


def test_keyword_hit_rate_no_keywords():
    assert keyword_hit_rate("任意回答", None) is None
    assert keyword_hit_rate("任意回答", "") is None


def test_keyword_hit_rate_case_insensitive():
    assert keyword_hit_rate("Use ORM framework", "orm,framework") == 1.0


def test_retrieval_metrics_hit():
    sources = [_source("SQL注入防护指南.md"), _source("XSS防护指南.md")]
    hit, precision, recall = retrieval_metrics(sources, "SQL注入防护指南", top_k=2)
    assert hit is True
    assert precision == 0.5
    assert recall == 1.0


def test_retrieval_metrics_miss():
    sources = [_source("XSS防护指南.md")]
    hit, precision, recall = retrieval_metrics(sources, "SQL注入防护指南", top_k=1)
    assert hit is False
    assert precision == 0.0
    assert recall == 0.0


def test_retrieval_metrics_no_expectation():
    hit, precision, recall = retrieval_metrics([_source()], None, top_k=1)
    assert hit is None and precision is None and recall is None


def test_precision_at_k_zero_sources():
    """阈值过滤后 0 条返回: 有期望来源时 P@K = 0/K = 0, 非零除异常。"""
    hit, precision, recall = retrieval_metrics([], "SQL注入防护指南", top_k=5)
    assert hit is False
    assert precision == 0.0
    assert recall == 0.0


def test_precision_at_k_fewer_than_k():
    """返回数 < K(如 K=10 仅 9 条): 分母仍为 K, 缺失位置按不相关计(标准 P@K)。"""
    sources = [_source("SQL注入防护指南.md")] + [_source("其他.md") for _ in range(8)]
    hit, precision, recall = retrieval_metrics(sources, "SQL注入防护指南", top_k=10)
    assert hit is True
    assert precision == 0.1  # 1/10, 而非 1/9
    assert recall == 1.0


def test_precision_at_k_exactly_k():
    """返回数恰好等于 K: 与按返回数作分母的旧口径一致。"""
    sources = [_source("SQL注入防护指南.md"), _source("SQL注入防护指南.md"),
               _source("XSS防护指南.md"), _source("XSS防护指南.md"), _source("CSRF防御指南.md")]
    hit, precision, recall = retrieval_metrics(sources, "SQL注入防护指南", top_k=5)
    assert hit is True
    assert precision == 0.4  # 2 个相关 chunk / 5
    assert recall == 1.0


def test_precision_at_k_multiple_relevant_chunks():
    """多相关 chunk: 同一期望文档命中多条时按条数计入分子。"""
    sources = [_source("SQL注入防护指南.md") for _ in range(3)] + [_source("XSS防护指南.md")]
    _, precision, _ = retrieval_metrics(sources, "SQL注入防护指南", top_k=4)
    assert precision == 0.75


def test_citation_validity_valid():
    answer = "应使用参数化查询 [1], 并开启最小权限 [2]。"
    assert citation_validity(answer, [_source(), _source()]) == 1.0


def test_citation_validity_out_of_range():
    answer = "根据资料 [3] 可知。"
    assert citation_validity(answer, [_source()]) == 0.0
    assert has_fabricated_citation(answer, [_source()]) is True


def test_citation_validity_partial():
    """部分编号越界: 有效数/引用总数。"""
    answer = "参数化查询 [1] 与最小权限 [9] 都有帮助。"
    assert citation_validity(answer, [_source(), _source()]) == 0.5


def test_citation_validity_no_citation_with_sources():
    assert citation_validity("直接回答", [_source()]) == 0.0


def test_citation_validity_no_sources_no_citation():
    assert citation_validity("直接回答", []) is None


def test_aggregate_metrics():
    results = [
        {"error": None, "retrieval_hit": True, "precision_at_k": 0.5, "recall_at_k": 1.0,
         "keyword_hit_rate": 0.8, "citation_matched": 1.0, "retrieval_time": 50,
         "generation_time": 500, "total_time": 550, "total_tokens": 120},
        {"error": None, "retrieval_hit": False, "precision_at_k": 0.0, "recall_at_k": 0.0,
         "keyword_hit_rate": 0.4, "citation_matched": 0.0, "retrieval_time": 30,
         "generation_time": 400, "total_time": 430, "total_tokens": 100},
        {"error": "LLM 超时", "retrieval_hit": None, "precision_at_k": None, "recall_at_k": None,
         "keyword_hit_rate": None, "citation_matched": None, "retrieval_time": 0,
         "generation_time": 0, "total_time": 0, "total_tokens": 0},
    ]
    agg = aggregate(results)
    assert agg["total"] == 3
    assert agg["completed"] == 2
    assert agg["failed"] == 1
    assert agg["retrieval_hit_rate"] == 0.5
    assert agg["precision_at_k"] == 0.25
    assert agg["recall_at_k"] == 0.5
    assert agg["answer_keyword_accuracy"] == 0.6
    assert agg["citation_validity"] == 0.5
    assert agg["avg_total_time_ms"] == 490.0
    assert agg["avg_total_tokens"] == 110.0


def test_aggregate_tokens_from_prompt_plus_completion():
    """EvalItemResult 无 total_tokens 字段, 应由 prompt+completion 求和。"""
    agg = aggregate([
        {"error": None, "prompt_tokens": 800, "completion_tokens": 200},
        {"error": None, "prompt_tokens": 600, "completion_tokens": 400},
    ])
    assert agg["avg_total_tokens"] == 1000.0


def pytest_approx(expected, tol=1e-3):
    class _Approx:
        def __eq__(self, other):
            return abs(other - expected) <= tol

    return _Approx()


def test_mrr_first_hit_rank():
    sources = [
        {"documentName": "A.pdf"},
        {"documentName": "OWASP API Security.pdf"},
        {"documentName": "C.md"},
    ]
    # 命中在第 2 位 → 1/2
    assert mrr(sources, "owasp api") == 0.5
    # 命中在第 1 位 → 1.0
    assert mrr(sources, "A.pdf") == 1.0
    # 全未命中 → 0.0
    assert mrr(sources, "不存在文档") == 0.0
    # 无期望来源 / 空结果 → None 不参与统计
    assert mrr(sources, None) is None
    assert mrr([], "A.pdf") is None


def test_aggregate_includes_mrr():
    results = [
        {"error": None, "mrr": 1.0, "precision_at_k": 0.5, "recall_at_k": 1.0,
         "keyword_hit_rate": 0.8, "citation_matched": 1.0,
         "retrieval_time": 10, "generation_time": 100, "total_time": 110},
        {"error": None, "mrr": 0.0, "precision_at_k": 0.0, "recall_at_k": 0.0,
         "keyword_hit_rate": 0.4, "citation_matched": 0.0,
         "retrieval_time": 20, "generation_time": 200, "total_time": 220},
    ]
    agg = aggregate(results)
    assert agg["mrr"] == 0.5


# ---------------- nDCG@K ----------------
def test_ndcg_first_position():
    """首位命中: DCG=1/log2(2)=1, IDCG=1 → nDCG=1.0"""
    from app.evaluation.metrics import ndcg_at_k
    import math
    sources = [_source(), _source("其他文档.md")]
    assert ndcg_at_k(sources, "SQL注入防护指南.md", 5) == 1.0


def test_ndcg_second_position_hand_computed():
    """手算对拍: 命中在第 2 位 → nDCG = (1/log2(3)) / (1/log2(2)) = 1/1.58496"""
    from app.evaluation.metrics import ndcg_at_k
    import math
    sources = [_source("无关文档A.md"), _source()]
    expected = round((1.0 / math.log2(3)) / (1.0 / math.log2(2)), 4)
    assert ndcg_at_k(sources, "SQL注入防护指南.md", 5) == expected


def test_ndcg_miss_is_zero():
    from app.evaluation.metrics import ndcg_at_k
    sources = [_source("无关文档A.md"), _source("无关文档B.md")]
    assert ndcg_at_k(sources, "SQL注入防护指南.md", 5) == 0.0


def test_ndcg_respects_k_cutoff():
    """命中位置超出 K 截断 → 0(与真实 Top-K 展示一致)"""
    from app.evaluation.metrics import ndcg_at_k
    sources = [_source("无关文档A.md"), _source("无关文档B.md"), _source()]
    assert ndcg_at_k(sources, "SQL注入防护指南.md", 2) == 0.0
    assert ndcg_at_k(sources, "SQL注入防护指南.md", 3) > 0


def test_ndcg_no_expectation_is_none():
    from app.evaluation.metrics import ndcg_at_k
    assert ndcg_at_k([_source()], None, 5) is None


def test_ndcg_ideal_ordering_beats_reversed():
    """排序质量: 相关文档靠前 nDCG 更高(标准实现的区分度)"""
    from app.evaluation.metrics import ndcg_at_k
    good = [_source(), _source("无关文档A.md"), _source("无关文档B.md")]
    bad = [_source("无关文档A.md"), _source("无关文档B.md"), _source()]
    assert ndcg_at_k(good, "SQL注入防护指南.md", 3) > ndcg_at_k(bad, "SQL注入防护指南.md", 3)


def test_aggregate_includes_ndcg_and_performance_detail():
    results = [
        {"error": None, "ndcg_at_k": 1.0, "rerank_used": True, "context_tokens": 800},
        {"error": None, "ndcg_at_k": 0.5, "rerank_used": False, "context_tokens": 1200},
        {"error": None, "ndcg_at_k": 0.0, "rerank_used": None, "context_tokens": None},
    ]
    agg = aggregate(results)
    assert agg["ndcg_at_k"] == 0.5
    assert agg["rerank_activation_rate"] == 0.5
    assert agg["avg_context_tokens"] == 1000.0
