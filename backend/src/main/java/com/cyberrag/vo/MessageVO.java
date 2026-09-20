package com.cyberrag.vo;

import com.cyberrag.dto.rag.ChatResponse;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 消息视图。
 */
@Data
@Builder
public class MessageVO {
    private Long id;
    private Long conversationId;
    private String role;
    private String content;
    private List<ChatResponse.SourceItem> sources;
    /** 本次 RAG 决策轨迹(阶段耗时/路由/门控/缓存; 普通用户折叠展示) */
    private Map<String, Object> trace;
    private Integer retrievalTime;
    private Integer generationTime;
    private Integer totalTokens;
    private LocalDateTime createdAt;
}
