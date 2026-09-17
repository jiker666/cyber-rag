package com.cyberrag.vo;

import com.cyberrag.dto.rag.ChatResponse;
import lombok.Builder;
import lombok.Data;

/**
 * 问答返回: 消息 ID + 会话 ID + 回答 + 引用来源。
 */
@Data
@Builder
public class AskVO {
    private Long conversationId;
    private Long userMessageId;
    private Long assistantMessageId;
    private ChatResponse response;
}
