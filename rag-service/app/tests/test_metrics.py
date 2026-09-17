"""评价指标测试。"""
from app.evaluation.metrics import (
    aggregate,
    citation_accuracy,
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


def test_citation_accuracy_valid():
    answer = "应使用参数化查询 [1], 并开启最小权限 [2]。"
    assert citation_accuracy(answer, [_source(), _source()]) == 1.0


def test_citation_accuracy_out_of_range():
    answer = "根据资料 [3] 可知。"
    assert citation_accuracy(answer, [_source()]) == 0.0
    assert has_fabricated_citation(answer, [_source()]) is True


def test_citation_accuracy_no_citation_with_sources():
    assert citation_accuracy("直接回答", [_source()]) == 0.0


def test_citation_accuracy_no_sources_no_citation():
    assert citation_accuracy("直接回答", []) is None


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
