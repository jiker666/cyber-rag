package com.cyberrag.dto.rag;

import lombok.Data;

import java.util.List;

/**
 * 批量评测请求(发往 Python 服务)。
 */
@Data
public class EvalBatchRequest {
    private String mode;
    private Long knowledgeBaseId;
    private EvalParams params;
    private List<EvalItem> items;

    @Data
    public static class EvalParams {
        private Integer topK;
        private Double temperature;
        private Double scoreThreshold;
        private Boolean enableReranker;
        private Integer rerankTopN;
        private String retrievalStrategy;
        // ---- Adaptive RAG(消融实验开关) ----
        private Boolean adaptive;
        private Boolean entityBoost;
        private Boolean rerankGating;
        private Boolean dynamicContext;
        private Boolean useCaches;
    }

    @Data
    public static class EvalItem {
        private Long itemId;
        private String question;
        private String referenceAnswer;
        private String expectedKeywords;
        private String expectedSource;
    }
}
