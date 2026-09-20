package com.cyberrag.dto.rag;

import lombok.Data;

import java.util.List;

/**
 * 批量评测响应(含汇总指标)。
 */
@Data
public class EvalBatchResponse {
    private List<EvalItemResult> results;
    private EvalMetrics metrics;

    @Data
    public static class EvalItemResult {
        private Long itemId;
        private String question;
        private String mode;
        private String answer;
        private List<ChatResponse.SourceItem> sources;
        private Integer retrievalTime;
        private Integer generationTime;
        private Integer totalTime;
        private Integer promptTokens;
        private Integer completionTokens;
        private Boolean retrievalHit;
        private Double precisionAtK;
        private Double recallAtK;
        private Double ndcgAtK;
        private Double mrr;
        private Double keywordHitRate;
        private Double citationMatched;
        /** Performance Detail: 自适应路由 */
        private String route;
        /** Performance Detail: 是否触发重排(null = 非自适应不统计) */
        private Boolean rerankUsed;
        /** Performance Detail: 送入 LLM 的上下文 token 数(启发式估算) */
        private Integer contextTokens;
        private String error;
    }

    @Data
    public static class EvalMetrics {
        private Integer total;
        private Integer completed;
        private Integer failed;
        private Double retrievalHitRate;
        private Double precisionAtK;
        private Double recallAtK;
        private Double ndcgAtK;
        private Double mrr;
        private Double answerKeywordAccuracy;
        /** 引用编号有效率(citation validity): [n] 是否指向真实返回来源, 非事实一致性验证 */
        private Double citationValidity;
        private Double avgRetrievalTimeMs;
        private Double avgGenerationTimeMs;
        private Double avgTotalTimeMs;
        private Double avgTotalTokens;
        /** 重排激活率(自适应模式: 触发重排的题目占比) */
        private Double rerankActivationRate;
        /** 平均上下文 token 数(启发式估算口径) */
        private Double avgContextTokens;
    }
}
