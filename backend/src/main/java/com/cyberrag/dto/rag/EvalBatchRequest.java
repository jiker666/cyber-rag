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
