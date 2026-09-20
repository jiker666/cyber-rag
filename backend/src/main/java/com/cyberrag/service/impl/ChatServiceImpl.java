package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.cyberrag.common.constants.Constants;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.chat.AskRequest;
import com.cyberrag.dto.rag.ChatRequest;
import com.cyberrag.dto.rag.ChatResponse;
import com.cyberrag.entity.Conversation;
import com.cyberrag.entity.Message;
import com.cyberrag.entity.QaRecord;
import com.cyberrag.entity.RagConfig;
import com.cyberrag.integration.RagServiceClient;
import com.cyberrag.mapper.ConversationMapper;
import com.cyberrag.mapper.MessageMapper;
import com.cyberrag.mapper.QaRecordMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.ChatService;
import com.cyberrag.service.RagConfigService;
import com.cyberrag.util.JsonUtil;
import com.cyberrag.vo.AskVO;
import com.cyberrag.vo.MessageVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 问答服务实现: 编排会话、消息、RAG 调用与问答记录。
 *
 * 流式路径(streamAsk)不在事务内长驻: 会话/用户消息在调用线程落库,
 * 回答在 SSE done 事件后由工作线程落库(各插入独立提交, 避免长事务占连接)。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatServiceImpl implements ChatService {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final QaRecordMapper qaRecordMapper;
    private final RagConfigService ragConfigService;
    private final RagServiceClient ragClient;

    /** 流式问答工作线程(与 Tomcat 请求线程解耦, SseEmitter 生命周期跨请求) */
    private static final ExecutorService STREAM_EXECUTOR = Executors.newFixedThreadPool(4, r -> {
        Thread t = new Thread(r, "chat-stream");
        t.setDaemon(true);
        return t;
    });

    /** 流式会话超时(评测级长回答也足够) */
    private static final long STREAM_TIMEOUT_MS = 300_000L;

    /** 提问准备结果: 流式与同步路径共用(record 与项目 Lombok 版本不兼容, 用普通类) */
    private static final class AskPreparation {
        private final Conversation conversation;
        private final Message userMsg;
        private final ChatRequest chatRequest;
        private final Long userId;

        private AskPreparation(Conversation conversation, Message userMsg,
                               ChatRequest chatRequest, Long userId) {
            this.conversation = conversation;
            this.userMsg = userMsg;
            this.chatRequest = chatRequest;
            this.userId = userId;
        }
    }

    // ------------------------------------------------------------------
    // 同步问答
    // ------------------------------------------------------------------

    @Override
    @Transactional
    public AskVO ask(AskRequest request) {
        AskPreparation prep = prepare(request);
        ChatResponse response = ragClient.chatQuery(prep.chatRequest);
        Message assistantMsg = finalizeAnswer(prep, response);

        log.info("问答完成: conversation={}, sources={}, totalTime={}ms",
                prep.conversation.getId(),
                response.getSources() == null ? 0 : response.getSources().size(),
                response.getTotalTime());

        return AskVO.builder()
                .conversationId(prep.conversation.getId())
                .userMessageId(prep.userMsg.getId())
                .assistantMessageId(assistantMsg.getId())
                .response(response)
                .build();
    }

    // ------------------------------------------------------------------
    // 流式问答(SSE)
    // ------------------------------------------------------------------

    @Override
    public SseEmitter streamAsk(AskRequest request) {
        // 1. 调用线程内完成校验与会话/用户消息落库(AuthContext 在此有效)
        AskPreparation prep = prepare(request);
        SseEmitter emitter = new SseEmitter(STREAM_TIMEOUT_MS);

        emitter.onTimeout(() -> log.warn("流式问答超时: conversation={}", prep.conversation.getId()));
        emitter.onError(e -> log.warn("流式问答连接异常: conversation={}, cause={}",
                prep.conversation.getId(), e.getMessage()));

        // 2. start 事件: 前端立即拿到会话/消息 ID
        sendEvent(emitter, Map.of(
                "type", "start",
                "conversationId", prep.conversation.getId(),
                "userMessageId", prep.userMsg.getId()));

        // 3. 工作线程转发 rag-service SSE 流(此线程无 AuthContext, 全部用 prep 携带的数据)
        STREAM_EXECUTOR.execute(() -> {
            try {
                ragClient.chatQueryStream(prep.chatRequest, event -> {
                    String type = String.valueOf(event.get("type"));
                    switch (type) {
                        case "done" -> {
                            // done 携带完整结果(答案/引用/Trace), 由服务端落库后再推给前端
                            ChatResponse response = JsonUtil.convert(
                                    event.get("result"), ChatResponse.class);
                            Message assistantMsg = finalizeAnswer(prep, response);
                            sendEvent(emitter, Map.of(
                                    "type", "done",
                                    "assistantMessageId", assistantMsg.getId(),
                                    "response", response));
                            emitter.complete();
                        }
                        default -> sendEvent(emitter, event); // start 后的 analysis / retrieval / delta / error
                    }
                });
            } catch (Exception e) {
                log.error("流式问答失败: conversation={}", prep.conversation.getId(), e);
                sendEvent(emitter, Map.of("type", "error", "message",
                        e.getMessage() == null ? "AI 服务流式调用失败" : e.getMessage()));
                emitter.complete();
            }
        });
        return emitter;
    }

    /** SSE 事件发送(失败仅告警, 不中断流转发) */
    private void sendEvent(SseEmitter emitter, Map<String, Object> data) {
        try {
            emitter.send(SseEmitter.event().data(JsonUtil.toJson(data), MediaType.APPLICATION_JSON));
        } catch (Exception e) {
            log.warn("SSE 事件推送失败(客户端可能已断开): {}", e.getMessage());
        }
    }

    // ------------------------------------------------------------------
    // 公共流程
    // ------------------------------------------------------------------

    /** 校验 + 会话获取/创建 + 用户消息落库 + RAG 请求组装(历史窗口截断)。 */
    private AskPreparation prepare(AskRequest request) {
        if (request.getQuestion() == null || request.getQuestion().isBlank()) {
            throw new BusinessException(422, "问题内容不能为空");
        }
        RagConfig config = ragConfigService.getConfig();

        Conversation conversation = obtainConversation(request.getConversationId(), request.getKnowledgeBaseId());
        if (!conversation.getUserId().equals(AuthContext.getUserId())) {
            throw new BusinessException(403, "无权访问该会话");
        }

        Message userMsg = saveMessage(conversation.getId(), Constants.MSG_USER, request.getQuestion(),
                null, null, 0, 0, 0);

        List<Message> history = messageMapper.selectList(new LambdaQueryWrapper<Message>()
                .eq(Message::getConversationId, conversation.getId())
                .lt(Message::getId, userMsg.getId())
                .orderByDesc(Message::getId)
                .last("LIMIT " + config.getHistoryWindow()));
        Collections.reverse(history);
        List<ChatRequest.HistoryMsg> historyMsgs = history.stream()
                .map(m -> new ChatRequest.HistoryMsg(m.getRole(), m.getContent()))
                .toList();

        ChatRequest chatRequest = ChatRequest.builder()
                .question(request.getQuestion())
                .knowledgeBaseIds(List.of(conversation.getKnowledgeBaseId()))
                .topK(request.getTopK() != null ? request.getTopK() : config.getTopK())
                .temperature(request.getTemperature() != null ? request.getTemperature()
                        : config.getTemperature().doubleValue())
                .scoreThreshold(config.getScoreThreshold().doubleValue())
                .enableReranker(request.getEnableReranker() != null ? request.getEnableReranker()
                        : config.getEnableReranker() == 1)
                .rerankTopN(config.getRerankTopN())
                .retrievalStrategy(config.getRetrievalStrategy() != null
                        ? config.getRetrievalStrategy() : "vector")
                .historyWindow(config.getHistoryWindow())
                .history(historyMsgs)
                .adaptive(config.getAdaptiveEnabled() != null && config.getAdaptiveEnabled() == 1)
                .build();
        return new AskPreparation(conversation, userMsg, chatRequest, AuthContext.getUserId());
    }

    /** 保存 AI 回答(含引用/Trace) + 维护会话计数 + 落问答记录。 */
    private Message finalizeAnswer(AskPreparation prep, ChatResponse response) {
        Conversation conversation = prep.conversation;
        Message assistantMsg = saveMessage(
                conversation.getId(), Constants.MSG_ASSISTANT, response.getAnswer(),
                JsonUtil.toJson(response.getSources()),
                response.getTrace() == null ? null : JsonUtil.toJson(response.getTrace()),
                nullToZero(response.getRetrievalTime()), nullToZero(response.getGenerationTime()),
                nullToZero(response.getTotalTokens()));

        conversation.setMessageCount(conversation.getMessageCount() == null ? 2 : conversation.getMessageCount() + 2);
        conversation.setLastMessageAt(LocalDateTime.now());
        conversationMapper.updateById(conversation);

        QaRecord record = new QaRecord();
        record.setUserId(prep.userId);
        record.setConversationId(conversation.getId());
        record.setKnowledgeBaseId(conversation.getKnowledgeBaseId());
        record.setQuestion(prep.userMsg.getContent());
        record.setAnswer(response.getAnswer());
        record.setSources(JsonUtil.toJson(response.getSources()));
        record.setTrace(response.getTrace() == null ? null : JsonUtil.toJson(response.getTrace()));
        record.setRetrievalTime(nullToZero(response.getRetrievalTime()));
        record.setGenerationTime(nullToZero(response.getGenerationTime()));
        record.setTotalTime(nullToZero(response.getTotalTime()));
        record.setTotalTokens(nullToZero(response.getTotalTokens()));
        qaRecordMapper.insert(record);
        return assistantMsg;
    }

    @Override
    @Transactional
    public AskVO regenerate(long conversationId) {
        Conversation conversation = conversationMapper.selectById(conversationId);
        checkConversationOwner(conversation);
        // 找到最后一条用户消息
        Message lastUser = messageMapper.selectList(new LambdaQueryWrapper<Message>()
                        .eq(Message::getConversationId, conversationId)
                        .eq(Message::getRole, Constants.MSG_USER)
                        .orderByDesc(Message::getId)
                        .last("LIMIT 1"))
                .stream().findFirst()
                .orElseThrow(() -> new BusinessException(400, "会话中没有可重新生成的问题"));

        AskRequest request = new AskRequest();
        request.setQuestion(lastUser.getContent());
        request.setConversationId(conversationId);
        request.setKnowledgeBaseId(conversation.getKnowledgeBaseId());
        return ask(request);
    }

    @Override
    public List<MessageVO> listMessages(long conversationId) {
        Conversation conversation = conversationMapper.selectById(conversationId);
        checkConversationOwner(conversation);
        List<Message> messages = messageMapper.selectList(new LambdaQueryWrapper<Message>()
                .eq(Message::getConversationId, conversationId)
                .orderByAsc(Message::getId));
        return messages.stream().map(this::toVO).toList();
    }

    @Override
    @Transactional
    public void clearMessages(long conversationId) {
        Conversation conversation = conversationMapper.selectById(conversationId);
        checkConversationOwner(conversation);
        messageMapper.delete(new LambdaQueryWrapper<Message>()
                .eq(Message::getConversationId, conversationId));
        conversation.setMessageCount(0);
        conversationMapper.updateById(conversation);
    }

    // ------------------------------------------------------------------

    private Conversation obtainConversation(Long conversationId, long knowledgeBaseId) {
        if (conversationId != null) {
            Conversation existing = conversationMapper.selectById(conversationId);
            if (existing == null) {
                throw new BusinessException(404, "会话不存在");
            }
            return existing;
        }
        Conversation created = new Conversation();
        created.setUserId(AuthContext.getUserId());
        created.setKnowledgeBaseId(knowledgeBaseId);
        created.setTitle("新对话");
        created.setMessageCount(0);
        created.setLastMessageAt(LocalDateTime.now());
        conversationMapper.insert(created);
        return created;
    }

    private Message saveMessage(Long conversationId, String role, String content, String sources,
                                String trace, int retrievalTime, int generationTime, int totalTokens) {
        Message msg = new Message();
        msg.setConversationId(conversationId);
        msg.setRole(role);
        msg.setContent(content);
        msg.setSources(sources);
        msg.setTrace(trace);
        msg.setRetrievalTime(retrievalTime);
        msg.setGenerationTime(generationTime);
        msg.setTotalTokens(totalTokens);
        messageMapper.insert(msg);
        return msg;
    }

    private void checkConversationOwner(Conversation conversation) {
        if (conversation == null) {
            throw new BusinessException(404, "会话不存在");
        }
        boolean admin = AuthContext.isAdmin();
        if (!admin && !conversation.getUserId().equals(AuthContext.getUserId())) {
            throw new BusinessException(403, "无权访问该会话");
        }
    }

    @SuppressWarnings("unchecked")
    private MessageVO toVO(Message m) {
        List<ChatResponse.SourceItem> sources = null;
        if (m.getSources() != null && !m.getSources().isBlank()) {
            try {
                sources = JsonUtil.fromJson(m.getSources(),
                        new com.fasterxml.jackson.core.type.TypeReference<List<ChatResponse.SourceItem>>() {
                        });
            } catch (Exception e) {
                log.warn("引用来源解析失败: messageId={}", m.getId());
            }
        }
        Map<String, Object> trace = null;
        if (m.getTrace() != null && !m.getTrace().isBlank()) {
            try {
                trace = JsonUtil.fromJson(m.getTrace(),
                        new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
                        });
            } catch (Exception e) {
                log.warn("RAG Trace 解析失败: messageId={}", m.getId());
            }
        }
        return MessageVO.builder()
                .id(m.getId())
                .conversationId(m.getConversationId())
                .role(m.getRole())
                .content(m.getContent())
                .sources(sources)
                .trace(trace)
                .retrievalTime(m.getRetrievalTime())
                .generationTime(m.getGenerationTime())
                .totalTokens(m.getTotalTokens())
                .createdAt(m.getCreatedAt())
                .build();
    }

    private int nullToZero(Integer value) {
        return value == null ? 0 : value;
    }
}
