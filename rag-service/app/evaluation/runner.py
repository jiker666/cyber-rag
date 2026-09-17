"""评测执行器: 批量运行 LLM_ONLY / RAG_LLM 并计算指标。"""
import logging

from app.evaluation import metrics
from app.models.schemas import EvalBatchRequest, EvalItemResult
from app.rag.pipeline import ChatHistoryItem, RagParams, RagPipeline

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
        )
        kb_ids = [request.knowledge_base_id] if request.knowledge_base_id else []
        results: list[EvalItemResult] = []
        for item in request.items:
            try:
                if request.mode == "LLM_ONLY":
                    res = self.pipeline.llm_only_chat(item.question, params)
                else:
                    res = self.pipeline.rag_chat(item.question, kb_ids, params, history=None)
                hit, precision, recall = metrics.retrieval_metrics(
                    res.sources, item.expected_source, params.top_k or 5
                )
                mrr_value = metrics.mrr(res.sources, item.expected_source)
                citation = (
                    metrics.citation_accuracy(res.answer, res.sources)
                    if request.mode == "RAG_LLM"
                    else None
                )
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
                        mrr=mrr_value,
                        keyword_hit_rate=metrics.keyword_hit_rate(
                            res.answer, item.expected_keywords
                        ),
                        citation_matched=citation,
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
