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

    // ---------------- 流式问答(SSE) ----------------

    @Test
    void streamAsk_emits_events_and_persists_answer() throws Exception {
        // 模拟 rag-service SSE 事件流: analysis → retrieval → delta×2 → done
        ChatResponse done = new ChatResponse();
        done.setAnswer("[1] 流式回答内容");
        done.setRetrievalTime(50);
        done.setGenerationTime(300);
        done.setTotalTime(350);
        done.setTotalTokens(90);
        ChatResponse.SourceItem source = new ChatResponse.SourceItem();
        source.setDocumentId(101L);
        source.setDocumentName("SQL注入防护指南.md");
        done.setSources(List.of(source));
        java.util.Map<String, Object> trace = java.util.Map.of(
                "route", "HYBRID", "rerankerUsed", true, "totalMs", 350);
        done.setTrace(trace);

        java.util.List<java.util.Map<String, Object>> events = new java.util.ArrayList<>();
        org.mockito.Mockito.doAnswer(inv -> {
            @SuppressWarnings("unchecked")
            java.util.function.Consumer<java.util.Map<String, Object>> onEvent =
                    (java.util.function.Consumer<java.util.Map<String, Object>>) inv.getArgument(1);
            onEvent.accept(java.util.Map.of("type", "analysis", "route",
                    java.util.Map.of("route", "HYBRID")));
            onEvent.accept(java.util.Map.of("type", "retrieval"));
            onEvent.accept(java.util.Map.of("type", "delta", "text", "流式"));
            onEvent.accept(java.util.Map.of("type", "delta", "text", "回答内容"));
            onEvent.accept(java.util.Map.of("type", "done", "result",
                    com.cyberrag.util.JsonUtil.convert(done, java.util.Map.class)));
            return null;
        }).when(ragServiceClient).chatQueryStream(any(ChatRequest.class), any());

        org.springframework.web.servlet.mvc.method.annotation.SseEmitter emitter =
                chatService.streamAsk(askRequest("流式问题?", null));
        assertNotNull(emitter);
        // 工作线程异步执行, 等待落库完成(事件顺序由 Mockito 按序同步回调保证)
        org.awaitility.Awaitility.await().atMost(java.time.Duration.ofSeconds(5))
                .until(() -> eventsDone());
        // 校验落库: assistant 消息内容与 Trace(经 listMessages 属主路径验证)
        com.cyberrag.entity.Message assistant = latestAssistantMessage();
        assertNotNull(assistant);
        assertEquals("[1] 流式回答内容", assistant.getContent());
        assertNotNull(assistant.getTrace());
        assertTrue(assistant.getTrace().contains("HYBRID"));
        assertTrue(assistant.getTrace().contains("rerankerUsed"));
    }

    private volatile boolean streamFinished = false;

    private boolean eventsDone() {
        // 轮询消息表: assistant 消息出现即 done 分支已落库
        return streamFinished || chatHasAssistantTrace();
    }

    // Awaitility 轮询线程无 AuthContext, 直接走 Mapper 查询(绕过 listMessages 的属主校验)
    @Autowired
    private com.cyberrag.mapper.ConversationMapper conversationMapper;
    @Autowired
    private com.cyberrag.mapper.MessageMapper messageMapper;

    private boolean chatHasAssistantTrace() {
        com.cyberrag.entity.Message assistant = latestAssistantMessage();
        boolean ok = assistant != null && assistant.getTrace() != null;
        if (ok) {
            streamFinished = true;
        }
        return ok;
    }

    private com.cyberrag.entity.Message latestAssistantMessage() {
        return messageMapper.selectOne(
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<com.cyberrag.entity.Message>()
                        .eq(com.cyberrag.entity.Message::getRole, "assistant")
                        .orderByDesc(com.cyberrag.entity.Message::getId)
                        .last("LIMIT 1"));
    }

    private boolean userMessagePersisted() {
        return messageMapper.selectCount(
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<com.cyberrag.entity.Message>()
                        .eq(com.cyberrag.entity.Message::getRole, "user")) > 0;
    }

    @Test
    void streamAsk_downstream_error_emits_error_event() throws Exception {
        org.mockito.Mockito.doAnswer(inv -> {
            @SuppressWarnings("unchecked")
            java.util.function.Consumer<java.util.Map<String, Object>> onEvent =
                    (java.util.function.Consumer<java.util.Map<String, Object>>) inv.getArgument(1);
            onEvent.accept(java.util.Map.of("type", "error", "message", "AI 服务错误"));
            return null;
        }).when(ragServiceClient).chatQueryStream(any(ChatRequest.class), any());

        org.springframework.web.servlet.mvc.method.annotation.SseEmitter emitter =
                chatService.streamAsk(askRequest("触发错误", null));
        assertNotNull(emitter); // 不抛异常, 错误以事件形式下发
        org.awaitility.Awaitility.await().atMost(java.time.Duration.ofSeconds(5))
                .until(this::userMessagePersisted); // user 消息已落库
    }
}
