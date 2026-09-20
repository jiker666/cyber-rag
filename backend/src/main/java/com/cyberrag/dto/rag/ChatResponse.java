package com.cyberrag.dto.rag;

import lombok.Data;

import java.util.List;
import java.util.Map;

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
    /** 本次 RAG 决策轨迹(阶段耗时/路由/门控/缓存, camelCase 与 rag-service 一致) */
    private Map<String, Object> trace;
    /** 查询分析结果(问题类型/实体/复杂度) */
    private Map<String, Object> analysis;
    /** 检索路由决策 */
    private Map<String, Object> route;
    /** 证据置信度(retrievalConfidence/level/label) */
    private Map<String, Object> confidence;

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
        /** vector | bm25 | both(双路共同命中) */
        private String matchType;
        /** 命中查询中的精确安全实体编号(CVE/CWE 等) */
        private Boolean entityMatched;
        /** 小到大分块: 父块编号(可回溯) */
        private Long parentChunkId;
    }
}
