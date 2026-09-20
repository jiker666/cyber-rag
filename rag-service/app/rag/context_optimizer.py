"""Dynamic Context Optimizer: 上下文去重/合并/预算控制。

替代"Top-K 个 chunk 全塞给 LLM"的粗放做法:
  1. 近重复删除(trigram Jaccard ≥ 0.75 → 保留分数高者)
  2. 同文档相邻 chunk 合并(chunk_index 连续 → 拼接, 减少编号碎片)
  3. 按相关性排序(入参已按 score/rerank 排序)
  4. Token 预算截断: 简单问题 2~3 块, 复杂问题 4~6 块, 上限 RAG_MAX_CONTEXT_TOKENS

Token 估算为启发式口径(GLM 系中文 ≈0.75 token/汉字, ASCII ≈0.28 token/字符),
绝对值不精确但口径一致, 用于预算控制与跨配置对比是充分的。
"""
import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.rag.analyzer import QueryAnalysis
from app.rag.retriever import RetrievedChunk

logger = logging.getLogger("cyber-rag.rag.context_optimizer")

def estimate_tokens(text: str) -> int:
    """启发式 Token 估算: CJK≈0.75/字, 其他≈0.28/字符。"""
    if not text:
        return 0
    cjk = len(re.findall(r"[一-鿿]", text))
    return int(cjk * 0.75 + (len(text) - cjk) * 0.28)


def _trigrams(chunk: RetrievedChunk) -> set[tuple]:
    """字符 trigram 集合, 挂在对象上记忆化(生命周期与对象一致, 无 id 复用风险)。"""
    cached = getattr(chunk, "_trigram_set", None)
    if cached is not None:
        return cached
    normalized = re.sub(r"\s+", "", chunk.content)
    grams = {tuple(normalized[i : i + 3]) for i in range(max(len(normalized) - 2, 0))}
    chunk._trigram_set = grams
    return grams


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def budget_chunk_count(complexity: float, settings) -> int:
    """复杂度 → 上下文块数预算: 2 + complexity/2.5, 夹在 [min, max]。"""
    target = 2 + round(complexity / 2.5)
    return max(settings.min_context_chunks, min(settings.max_context_chunks, target))


@dataclass
class ContextSelection:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    context_tokens: int = 0
    dropped_duplicates: int = 0
    merged_adjacent: int = 0
    dropped_by_budget: int = 0


def optimize_context(
    chunks: list[RetrievedChunk],
    analysis: QueryAnalysis | None = None,
    token_budget: int | None = None,
    chunk_budget: int | None = None,
) -> ContextSelection:
    """入口: 输入已按相关性降序的候选, 输出预算内的最终上下文。

    small-to-large 场景下传入的已是父块(去重完成), 本函数对父块同样适用。
    """
    settings = get_settings()
    if not chunks:
        return ContextSelection()
    complexity = analysis.complexity if analysis else 5.0
    budget_tokens = token_budget if token_budget is not None else settings.max_context_tokens
    budget_chunks = chunk_budget if chunk_budget is not None else budget_chunk_count(complexity, settings)

    kept: list[RetrievedChunk] = []
    dropped_dup = 0
    # 1) 近重复删除(与已保留集合逐一比较)
    for chunk in chunks:
        dup = False
        for k in kept:
            if (
                k.document_id == chunk.document_id
                and k.knowledge_base_id == chunk.knowledge_base_id
                and _jaccard(_trigrams(k), _trigrams(chunk)) >= 0.75
            ):
                dup = True
                break
        if dup:
            dropped_dup += 1
        else:
            kept.append(chunk)

    # 2) 同文档相邻 chunk 合并(chunk_index 连续且都进入预算候选)
    merged = _merge_adjacent(kept)

    # 3) Token 与块数预算
    final: list[RetrievedChunk] = []
    used_tokens = 0
    dropped_budget = 0
    for chunk in merged:
        if len(final) >= budget_chunks:
            dropped_budget = len(merged) - len(final)
            break
        cost = estimate_tokens(chunk.content)
        if final and used_tokens + cost > budget_tokens:
            dropped_budget = len(merged) - len(final)
            break
        final.append(chunk)
        used_tokens += cost

    result = ContextSelection(
        chunks=final,
        context_tokens=used_tokens,
        dropped_duplicates=dropped_dup,
        merged_adjacent=len(kept) - len(merged) if len(merged) < len(kept) else 0,
        dropped_by_budget=dropped_budget,
    )
    logger.info(
        "上下文优化: 候选=%d → 去重-%d → 合并-%d → 预算截断-%d → 最终=%d (%d tokens)",
        len(chunks), dropped_dup, result.merged_adjacent, dropped_budget, len(final), used_tokens,
    )
    return result


def _merge_adjacent(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """同文档、chunk_index 连续的块合并为一个(保留高分块的元数据, 拼接内容)。

    仅当相邻块在排序列表中紧邻时合并, 避免打乱全局相关性次序。
    """
    if not chunks:
        return []
    out: list[RetrievedChunk] = [chunks[0]]
    for chunk in chunks[1:]:
        last = out[-1]
        if (
            last.document_id == chunk.document_id
            and last.knowledge_base_id == chunk.knowledge_base_id
            and abs(last.chunk_index - chunk.chunk_index) == 1
            and chunk.chunk_index > last.chunk_index
            and len(last.content) + len(chunk.content) <= 2600  # 合并上限, 防止超长上下文
        ):
            last.content = last.content + "\n" + chunk.content
        else:
            out.append(chunk)
    return out
