package com.cyberrag.dto.rag;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 与 Python RAG 服务交互的 DTO(字段与 FastAPI 模型保持一致)。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatRequest {
    private String question;
    private List<Long> knowledgeBaseIds;
    private Integer topK;
    private Double temperature;
    private Double scoreThreshold;
    private Boolean enableReranker;
    private Integer rerankTopN;
    private Integer historyWindow;
    private List<HistoryMsg> history;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class HistoryMsg {
        private String role;
        private String content;
    }
}
