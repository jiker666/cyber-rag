package com.cyberrag.vo;

import com.cyberrag.dto.rag.ChatResponse;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

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
    private Integer retrievalTime;
    private Integer generationTime;
    private Integer totalTokens;
    private LocalDateTime createdAt;
}
