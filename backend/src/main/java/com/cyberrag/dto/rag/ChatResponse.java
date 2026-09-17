package com.cyberrag.dto.rag;

import lombok.Data;

import java.util.List;

/**
 * RAG 问答响应。
 */
@Data
public class ChatResponse {
    private String answer;
    private List<SourceItem> sources;
    private Integer retrievalTime;
    private Integer generationTime;
    private Integer totalTime;
    private Integer promptTokens;
    private Integer completionTokens;
    private Integer totalTokens;
    private Integer retrievedCount;

    @Data
    public static class SourceItem {
        private Long documentId;
        private String documentName;
        private Long knowledgeBaseId;
        private Integer chunkIndex;
        private String source;
        private Integer page;
        private String content;
        private Double score;
        private Double rerankScore;
    }
}
