"""评测执行器: 批量运行 LLM_ONLY / RAG_LLM 并计算指标。"""
import logging

from app.evaluation import metrics
from app.models.schemas import EvalBatchRequest, EvalItemResult
from app.rag.pipeline import RagParams, RagPipeline

logger = logging.getLogger("cyber-rag.evaluation.runner")


class EvaluationRunner:
    """批量评测: 逐题真实运行, 不伪造任何数据; 单题失败记录错误并继续。"""

    def __init__(self, pipeline: RagPipeline | None = None):
        self.pipeline = pipeline or RagPipeline()

    def run_batch(self, request: EvalBatchRequest) -> tuple[list[EvalItemResult], dict]:
        params = RagParams(
            top_k=request.params.top_k,
            temperature=request.params.temperature,
            score_threshold=request.params.score_threshold,
            enable_reranker=request.params.enable_reranker,
            rerank_top_n=request.params.rerank_top_n,
            retrieval_strategy=request.params.retrieval_strategy,
            adaptive=request.params.adaptive,
            entity_boost=request.params.entity_boost,
            rerank_gating=request.params.rerank_gating,
            dynamic_context=request.params.dynamic_context,
            use_caches=request.params.use_caches,
        )
        effective_k = params.top_k or 5
        kb_ids = [request.knowledge_base_id] if request.knowledge_base_id else []
        results: list[EvalItemResult] = []
        for item in request.items:
            try:
                if request.mode == "LLM_ONLY":
                    res = self.pipeline.llm_only_chat(item.question, params)
                    # LLM_ONLY 无检索, 检索/引用类指标不适用(记 None, 不落 0)
                    hit = precision = recall = ndcg = mrr_value = citation = None
                else:
                    res = self.pipeline.rag_chat(item.question, kb_ids, params, history=None)
                    hit, precision, recall = metrics.retrieval_metrics(
                        res.sources, item.expected_source, effective_k
                    )
                    ndcg = metrics.ndcg_at_k(res.sources, item.expected_source, effective_k)
                    mrr_value = metrics.mrr(res.sources, item.expected_source)
                    citation = metrics.citation_validity(res.answer, res.sources)
                trace = res.trace or {}
                route = trace.get("route", "")
                rerank_used = trace.get("rerankerUsed") if trace else None
                context_tokens = trace.get("contextTokens") if trace else None
                results.append(
                    EvalItemResult(
                        item_id=item.item_id,
                        question=item.question,
                        mode=request.mode,
                        answer=res.answer,
                        sources=[s for s in res.sources],
                        retrieval_time=res.retrieval_time,
                        generation_time=res.generation_time,
                        total_time=res.total_time,
                        prompt_tokens=res.prompt_tokens,
                        completion_tokens=res.completion_tokens,
                        retrieval_hit=hit,
                        precision_at_k=precision,
                        recall_at_k=recall,
                        ndcg_at_k=ndcg,
                        mrr=mrr_value,
                        keyword_hit_rate=metrics.keyword_hit_rate(
                            res.answer, item.expected_keywords
                        ),
                        citation_matched=citation,
                        route=str(route or ""),
                        rerank_used=(
                            bool(rerank_used) if rerank_used is not None else None
                        ),
                        context_tokens=int(context_tokens) if context_tokens is not None else None,
                    )
                )
            except Exception as e:  # 单题失败不影响整体
                logger.exception("评测题目失败: item_id=%s", item.item_id)
                results.append(
                    EvalItemResult(
                        item_id=item.item_id,
                        question=item.question,
                        mode=request.mode,
                        answer="",
                        error=str(e)[:500],
                    )
                )
        agg = metrics.aggregate([r.model_dump() for r in results])
        logger.info(
            "评测批次完成: mode=%s, %d 题, 失败 %d",
            request.mode, len(results), agg.get("failed", 0),
        )
        return results, agg
