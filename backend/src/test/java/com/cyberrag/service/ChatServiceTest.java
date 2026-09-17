package com.cyberrag.service;

import com.cyberrag.BaseTest;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.chat.AskRequest;
import com.cyberrag.dto.rag.ChatRequest;
import com.cyberrag.dto.rag.ChatResponse;
import com.cyberrag.vo.AskVO;
import com.cyberrag.vo.MessageVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 问答链路测试: Mock RAG 服务返回, 校验会话/消息/引用来源/问答记录落库。
 */
class ChatServiceTest extends BaseTest {

    @Autowired
    private ChatService chatService;

    @BeforeEach
    void mockRagResponse() {
        ChatResponse response = new ChatResponse();
        response.setAnswer("[1] 应使用参数化查询防止 SQL 注入。");
        ChatResponse.SourceItem source = new ChatResponse.SourceItem();
        source.setDocumentId(101L);
        source.setDocumentName("SQL注入防护指南.md");
        source.setPage(3);
        source.setContent("使用参数化查询与预编译语句。");
        source.setScore(0.88);
        response.setSources(List.of(source));
        response.setRetrievalTime(120);
        response.setGenerationTime(800);
        response.setTotalTime(920);
        response.setTotalTokens(150);
        when(ragServiceClient.chatQuery(any(ChatRequest.class))).thenReturn(response);
    }

    private AskRequest askRequest(String question, Long conversationId) {
        AskRequest request = new AskRequest();
        request.setQuestion(question);
        request.setKnowledgeBaseId(1L);
        request.setConversationId(conversationId);
        return request;
    }

    @Test
    void ask_creates_conversation_and_saves_messages() {
        AskVO vo = chatService.ask(askRequest("如何防御 SQL 注入?", null));
        assertNotNull(vo.getConversationId());
        assertNotNull(vo.getUserMessageId());
        assertNotNull(vo.getAssistantMessageId());
        assertTrue(vo.getResponse().getAnswer().contains("[1]"));

        List<MessageVO> messages = chatService.listMessages(vo.getConversationId());
        assertEquals(2, messages.size());
        assertEquals("user", messages.get(0).getRole());
        assertEquals("assistant", messages.get(1).getRole());
        assertEquals(1, messages.get(1).getSources().size());
        assertEquals("SQL注入防护指南.md", messages.get(1).getSources().get(0).getDocumentName());
    }

    @Test
    void ask_reuses_existing_conversation_and_passes_history() {
        AskVO first = chatService.ask(askRequest("第一个问题", null));
        AskVO second = chatService.ask(askRequest("第二个问题", first.getConversationId()));
        assertEquals(first.getConversationId(), second.getConversationId());
        assertEquals(4, chatService.listMessages(first.getConversationId()).size());

        ArgumentCaptor<ChatRequest> captor = ArgumentCaptor.forClass(ChatRequest.class);
        verify(ragServiceClient, org.mockito.Mockito.atLeastOnce()).chatQuery(captor.capture());
        ChatRequest lastRequest = captor.getValue();
        assertEquals(2, lastRequest.getHistory().size());
        assertEquals("第二个问题", lastRequest.getQuestion());
    }

    @Test
    void regenerate_repeats_last_question() {
        AskVO first = chatService.ask(askRequest("唯一的问题", null));
        AskVO regenerated = chatService.regenerate(first.getConversationId());
        assertEquals(first.getConversationId(), regenerated.getConversationId());
        assertEquals(4, chatService.listMessages(first.getConversationId()).size());
    }

    @Test
    void clearMessages_empties_conversation() {
        AskVO vo = chatService.ask(askRequest("待清空", null));
        chatService.clearMessages(vo.getConversationId());
        assertEquals(0, chatService.listMessages(vo.getConversationId()).size());
    }

    @Test
    void ask_with_blank_question_rejected() {
        AskRequest request = askRequest(" ", null);
        assertThrows(Exception.class, () -> chatService.ask(request));
    }
}
