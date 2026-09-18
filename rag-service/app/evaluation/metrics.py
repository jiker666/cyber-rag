"""评价指标计算: 检索指标 + 答案指标, 全部基于真实运行结果。"""
import logging
import re
import statistics

logger = logging.getLogger("cyber-rag.evaluation.metrics")

# 回答中出现的引用编号, 如 [1] [2]
_CITATION_RE = re.compile(r"\[(\d{1,2})\]")


def keyword_hit_rate(answer: str, expected_keywords: str | None) -> float | None:
    """答案关键词命中率: 命中关键词数 / 期望关键词总数。"""
    if not expected_keywords:
        return None
    keywords = [k.strip() for k in re.split(r"[,，;；]", expected_keywords) if k.strip()]
    if not keywords:
        return None
    answer_lower = answer.lower()
    # 中文关键词与答案常存在无意义空格差异(如 "SQL注入" vs "SQL 注入"), 去空白后二次匹配
    answer_ns = re.sub(r"\s+", "", answer_lower)
    hit = sum(
        1
        for k in keywords
        if k.lower() in answer_lower or re.sub(r"\s+", "", k.lower()) in answer_ns
    )
    return round(hit / len(keywords), 4)


def retrieval_metrics(
    sources: list[dict], expected_source: str | None, top_k: int
) -> tuple[bool | None, float | None, float | None]:
    """基于期望来源文档计算检索指标。

    - Retrieval Hit: Top-K 检索结果中是否出现期望来源文档
    - Precision@K: 标准口径 P@K = Top-K 截断内相关片段数 / K。
      相似度阈值过滤导致实际返回数 < K 时, 缺失位置按不相关计(分母仍为 K)。
    - Recall@K: 文档级别, 期望文档被召回则为 1 否则 0(单期望来源下与 Hit 等价)
    """
    if not expected_source:
        return None, None, None
    k = max(top_k, 1)
    expected = expected_source.strip().lower()
    relevant = sum(
        1 for s in sources
        if expected in str(s.get("documentName", "")).lower()
        or expected in str(s.get("source", "")).lower()
    )
    hit = relevant > 0
    precision = round(relevant / k, 4)
    recall = 1.0 if hit else 0.0
    return hit, precision, recall


def mrr(sources: list[dict], expected_source: str | None) -> float | None:
    """MRR: 首个相关来源的倒数排名(全未命中为 0.0)。

    适用于期望来源单一/文档级标注的数据集; 无期望来源返回 None 不参与统计。
    """
    if not expected_source or not sources:
        return None
    expected = expected_source.strip().lower()
    for rank, s in enumerate(sources, start=1):
        if expected in str(s.get("documentName", "")).lower() or expected in str(
            s.get("source", "")
        ).lower():
            return round(1.0 / rank, 4)
    return 0.0


def citation_validity(answer: str, sources: list[dict]) -> float | None:
    """引用编号有效率(Citation Validity): 回答中引用编号是否真实存在于返回的来源列表。

    仅校验 [n] 编号是否指向实际返回的检索来源(1 ≤ n ≤ len(sources)),
    **不验证被引用文本在语义上是否支持该结论**, 不等价于事实一致性(faithfulness)验证。
    无引用且无来源 → None(不统计); 引用编号越界或来源为空却标注引用 → 视为无效引用。
    """
    if not sources:
        # 无来源时不应出现引用编号
        return None if not _CITATION_RE.search(answer) else 0.0
    citations = _CITATION_RE.findall(answer)
    if not citations:
        return 0.0  # RAG 模式有来源但未引用 → 0
    valid = sum(1 for c in citations if 1 <= int(c) <= len(sources))
    return round(valid / len(citations), 4)


# 兼容别名: 早期版本命名, 语义上该指标并非"准确率"
citation_accuracy = citation_validity


def has_fabricated_citation(answer: str, sources: list[dict]) -> bool:
    """引用幻觉判定: 回答引用了不存在的编号。"""
    citations = _CITATION_RE.findall(answer)
    if not citations:
        return False
    return any(int(c) > len(sources) or int(c) < 1 for c in citations)


def aggregate(results: list[dict]) -> dict:
    """汇总批量为整体指标; None 字段表示无法计算(如缺少期望来源)。"""
    completed = [r for r in results if r.get("error") is None]
    failed = len(results) - len(completed)
    agg: dict = {"total": len(results), "completed": len(completed), "failed": failed}

    def _avg(key: str, values: list) -> None:
        vals = [v for v in values if v is not None]
        agg[key] = round(statistics.fmean(vals), 4) if vals else None

    hits = [r.get("retrieval_hit") for r in completed if r.get("retrieval_hit") is not None]
    if completed and any(r.get("retrieval_hit") is not None for r in completed):
        _avg("retrieval_hit_rate", hits)
    _avg("precision_at_k", [r.get("precision_at_k") for r in completed])
    _avg("recall_at_k", [r.get("recall_at_k") for r in completed])
    _avg("mrr", [r.get("mrr") for r in completed])
    _avg("answer_keyword_accuracy", [r.get("keyword_hit_rate") for r in completed])
    _avg("citation_validity", [r.get("citation_matched") for r in completed])
    _avg("avg_retrieval_time_ms", [float(r.get("retrieval_time", 0)) for r in completed])
    _avg("avg_generation_time_ms", [float(r.get("generation_time", 0)) for r in completed])
    _avg("avg_total_time_ms", [float(r.get("total_time", 0)) for r in completed])
    # EvalItemResult 只落 prompt/completion 两项, 总 tokens 取二者之和
    _avg("avg_total_tokens", [
        float(r.get("total_tokens") or (r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)))
        for r in completed
    ])
    return agg
