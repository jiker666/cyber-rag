"""Adaptive Retrieval Routing + Confidence-aware Reranker Gating + Evidence Confidence。

路由决策(decide_route)在检索前基于 QueryAnalysis 选择路径:
  EXACT    精确安全实体问题: hybrid + entity exact boost, 编号强匹配优先
  FAST     简单事实/概念题: vector Top-3, top1 相似度与 top1-top2 间隔足够则直接生成
  HYBRID   一般语义/过程题: vector ∥ BM25 → RRF → 门控重排
  DECOMPOSE 复杂/比较/多跳题: LLM 分解子查询(严格门控) → 并行检索 → 融合

重排门控(should_rerank)基于检索信号而非固定开关:
  need_rerank = f(top1_score, score_margin, vector_bm25_agreement, complexity, candidate_count)
所有阈值来自配置(RAG_* 环境变量), 实验校准, 不存在"神奇分数"。
"""
import logging
import math
from dataclasses import dataclass

from app.core.config import get_settings
from app.rag.analyzer import (
    COMPARATIVE,
    EXACT_ENTITY,
    FACTUAL,
    MULTI_HOP,
    QueryAnalysis,
)

logger = logging.getLogger("cyber-rag.rag.adaptive")

ROUTE_EXACT = "EXACT"
ROUTE_FAST = "FAST"
ROUTE_HYBRID = "HYBRID"
ROUTE_DECOMPOSE = "DECOMPOSE"

# 证据置信度分级阈值(可解释口径, 非"答案正确概率")
CONF_SUFFICIENT = 0.65
CONF_MODERATE = 0.40


@dataclass
class RouteDecision:
    """一次问答的检索路径决策。"""

    route: str
    strategy: str  # vector | hybrid
    top_k: int
    rerank_policy: str  # skip(不重排) | auto(门控) | force(强制)
    need_decompose: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "route": self.route,
            "strategy": self.strategy,
            "topK": self.top_k,
            "rerankPolicy": self.rerank_policy,
            "needDecompose": self.need_decompose,
            "reason": self.reason,
        }


def decide_route(analysis: QueryAnalysis) -> RouteDecision:
    """基于查询分析选择检索路径。纯函数, 便于单元测试与消融。"""
    settings = get_settings()
    if analysis.query_type == MULTI_HOP and analysis.complexity >= settings.complexity_threshold:
        return RouteDecision(
            route=ROUTE_DECOMPOSE,
            strategy="hybrid",
            top_k=analysis.recommended_top_k,
            rerank_policy="force",
            need_decompose=True,
            reason=f"多跳问题(复杂度 {analysis.complexity}≥{settings.complexity_threshold}), 分解子查询并行检索",
        )
    if analysis.query_type == EXACT_ENTITY or analysis.exact_identifiers:
        return RouteDecision(
            route=ROUTE_EXACT,
            strategy="hybrid",
            top_k=max(analysis.recommended_top_k, 5),
            rerank_policy="auto",
            need_decompose=False,
            reason=f"包含精确实体 {'/'.join(analysis.exact_identifiers[:3])}, BM25 精确匹配优先 + 实体加权",
        )
    if analysis.query_type == COMPARATIVE:
        return RouteDecision(
            route=ROUTE_HYBRID,
            strategy="hybrid",
            top_k=analysis.recommended_top_k,
            rerank_policy="force",
            need_decompose=False,
            reason="比较类问题, 双路召回并强制重排区分相近候选",
        )
    if analysis.query_type in (FACTUAL,) and analysis.complexity <= 3.0:
        return RouteDecision(
            route=ROUTE_FAST,
            strategy="vector",
            top_k=3,
            rerank_policy="skip",
            need_decompose=False,
            reason="简单事实题, 尝试向量 Top-3 直出(置信不足时升级为 HYBRID)",
        )
    # CONCEPT / PROCEDURAL / 低复杂度 MULTI_HOP → 常规混合
    return RouteDecision(
        route=ROUTE_HYBRID,
        strategy="hybrid",
        top_k=analysis.recommended_top_k,
        rerank_policy="auto",
        need_decompose=False,
        reason=f"{analysis.query_type} 类问题, 混合检索 + 置信度门控重排",
    )


# ---------------------------------------------------------------- 重排门控

@dataclass
class RetrievalSignals:
    """门控与置信度计算的输入信号(检索阶段收集)。"""

    top1_score: float | None = None  # 融合后 top1 的余弦相似度(BM25 独有命中为 None)
    top2_score: float | None = None
    score_margin: float | None = None  # top1 - top2
    agreement: float | None = None  # vector/BM25 Top-5 重合率(单路检索为 None)
    candidate_count: int = 0
    rerank_top1: float | None = None  # 已重排时 CrossEncoder top1 分(logit)


def should_rerank(
    decision: RouteDecision,
    analysis: QueryAnalysis,
    signals: RetrievalSignals,
) -> tuple[bool, str]:
    """Confidence-aware Reranker Gating。

    规则(按优先级, 全部阈值来自配置):
    1. 路由策略 skip → 不重排(FAST 路径已判定高置信)
    2. 路由策略 force → 重排(比较/多跳需精排区分相近候选)
    3. 候选过少(≤3) → 不重排(重排对少量候选无区分度收益)
    4. 检索高置信(top1≥conf_thr 且 margin≥margin_thr 且 agreement≥agree_thr) → 不重排
    5. top1/top2 分差小(margin<margin_thr) → 重排(排序不稳定)
    6. top1 相似度不足(<conf_thr) → 重排(语义信号弱)
    7. 复杂度高于阈值 → 重排
    8. 默认不重排
    """
    settings = get_settings()
    if decision.rerank_policy == "skip":
        return False, "FAST 路径: 简单问题且检索高置信, 跳过重排"
    if decision.rerank_policy == "force":
        return True, f"{decision.route} 路径: {'多跳' if decision.need_decompose else '比较'}类问题强制重排"
    if signals.candidate_count <= 3:
        return False, f"候选仅 {signals.candidate_count} 条, 重排无区分度收益"
    if (
        signals.top1_score is not None
        and signals.top1_score >= settings.rerank_confidence_threshold
        and (signals.score_margin is not None and signals.score_margin >= settings.rerank_score_margin_threshold)
        and (signals.agreement is None or signals.agreement >= settings.rerank_agreement_threshold)
    ):
        return False, (
            f"检索置信度高(top1={signals.top1_score:.3f}≥{settings.rerank_confidence_threshold}, "
            f"margin={signals.score_margin:.3f}, agreement={signals.agreement if signals.agreement is not None else 'N/A'}), 跳过重排"
        )
    if signals.score_margin is not None and signals.score_margin < settings.rerank_score_margin_threshold:
        return True, f"top1/top2 分差小(margin={signals.score_margin:.3f}<{settings.rerank_score_margin_threshold}), 需重排稳定排序"
    if signals.top1_score is not None and signals.top1_score < settings.rerank_confidence_threshold:
        return True, f"top1 相似度不足({signals.top1_score:.3f}<{settings.rerank_confidence_threshold}), 语义信号弱需重排"
    if analysis.complexity >= settings.complexity_threshold:
        return True, f"问题复杂度 {analysis.complexity}≥{settings.complexity_threshold}, 启用重排"
    return False, "检索信号充分, 跳过重排"


# ---------------------------------------------------------------- 证据置信度

def retrieval_confidence(signals: RetrievalSignals, top_k: int) -> tuple[float, str]:
    """检索置信度: 由 Top1 相关性、排序间隔、双路一致性、证据数量综合。

    明确定义为"检索证据充分程度"的启发式评分 ∈ [0,1], **不是**答案正确概率:
      conf = 0.55×top1信号 + 0.20×双路一致 + 0.15×min(margin/0.15,1) + 0.10×min(n/K,1)
    已重排时 top1 信号 = 0.5×余弦 + 0.5×sigmoid(CrossEncoder logit)。
    """
    if signals.candidate_count == 0:
        return 0.0, "insufficient"
    top1 = signals.top1_score or 0.0
    if signals.rerank_top1 is not None:
        top1 = 0.5 * top1 + 0.5 * (1.0 / (1.0 + math.exp(-signals.rerank_top1)))
    agreement = signals.agreement if signals.agreement is not None else 0.5  # 单路检索取中性值
    margin_term = min((signals.score_margin or 0.0) / 0.15, 1.0)
    count_term = min(signals.candidate_count / max(top_k, 1), 1.0)
    conf = 0.55 * top1 + 0.20 * agreement + 0.15 * margin_term + 0.10 * count_term
    conf = round(min(max(conf, 0.0), 1.0), 4)
    level = "sufficient" if conf >= CONF_SUFFICIENT else ("moderate" if conf >= CONF_MODERATE else "insufficient")
    return conf, level


CONFIDENCE_LABELS = {"sufficient": "证据充分", "moderate": "证据一般", "insufficient": "证据不足"}
