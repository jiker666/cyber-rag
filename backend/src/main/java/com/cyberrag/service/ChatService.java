package com.cyberrag.service;

import com.cyberrag.dto.chat.AskRequest;
import com.cyberrag.vo.AskVO;
import com.cyberrag.vo.MessageVO;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

/**
 * 智能问答服务。
 */
public interface ChatService {

    /** RAG 问答: 保存消息 → 调用 AI 服务 → 保存回答与引用 */
    AskVO ask(AskRequest request);

    /** RAG 流式问答: SSE 逐 token 推送, 完成后保存回答与引用 */
    SseEmitter streamAsk(AskRequest request);

    /** 重新生成: 重新执行会话中最后一个用户问题 */
    AskVO regenerate(long conversationId);

    /** 会话消息列表 */
    List<MessageVO> listMessages(long conversationId);

    /** 清空会话消息(保留会话) */
    void clearMessages(long conversationId);
}
