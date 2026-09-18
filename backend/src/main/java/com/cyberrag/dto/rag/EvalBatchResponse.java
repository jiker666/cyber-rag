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
        private Double mrr;
        private Double keywordHitRate;
        private Double citationMatched;
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
        private Double mrr;
        private Double answerKeywordAccuracy;
        /** 引用编号有效率(citation validity): [n] 是否指向真实返回来源, 非事实一致性验证 */
        private Double citationValidity;
        private Double avgRetrievalTimeMs;
        private Double avgGenerationTimeMs;
        private Double avgTotalTimeMs;
        private Double avgTotalTokens;
    }
}
