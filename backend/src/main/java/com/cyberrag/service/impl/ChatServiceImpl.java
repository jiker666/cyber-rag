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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 问答服务实现: 编排会话、消息、RAG 调用与问答记录。
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

    @Override
    @Transactional
    public AskVO ask(AskRequest request) {
        if (request.getQuestion() == null || request.getQuestion().isBlank()) {
            throw new BusinessException(422, "问题内容不能为空");
        }
        RagConfig config = ragConfigService.getConfig();

        // 1. 会话获取/创建
        Conversation conversation = obtainConversation(request.getConversationId(), request.getKnowledgeBaseId());
        if (!conversation.getUserId().equals(AuthContext.getUserId())) {
            throw new BusinessException(403, "无权访问该会话");
        }

        // 2. 保存用户消息
        Message userMsg = saveMessage(conversation.getId(), Constants.MSG_USER, request.getQuestion(), null, 0, 0, 0);

        // 3. 组装历史(当前问题之前的消息, 按 history_window 截断)
        List<Message> history = messageMapper.selectList(new LambdaQueryWrapper<Message>()
                .eq(Message::getConversationId, conversation.getId())
                .lt(Message::getId, userMsg.getId())
                .orderByDesc(Message::getId)
                .last("LIMIT " + config.getHistoryWindow()));
        java.util.Collections.reverse(history);
        List<ChatRequest.HistoryMsg> historyMsgs = history.stream()
                .map(m -> new ChatRequest.HistoryMsg(m.getRole(), m.getContent()))
                .toList();

        // 4. 调用 RAG 服务
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
                .historyWindow(config.getHistoryWindow())
                .history(historyMsgs)
                .build();
        ChatResponse response = ragClient.chatQuery(chatRequest);

        // 5. 保存 AI 回答(含引用来源)
        Message assistantMsg = saveMessage(
                conversation.getId(), Constants.MSG_ASSISTANT, response.getAnswer(),
                JsonUtil.toJson(response.getSources()),
                nullToZero(response.getRetrievalTime()), nullToZero(response.getGenerationTime()),
                nullToZero(response.getTotalTokens()));

        // 6. 维护会话与问答记录
        conversation.setMessageCount(conversation.getMessageCount() == null ? 2 : conversation.getMessageCount() + 2);
        conversation.setLastMessageAt(LocalDateTime.now());
        conversationMapper.updateById(conversation);

        QaRecord record = new QaRecord();
        record.setUserId(AuthContext.getUserId());
        record.setConversationId(conversation.getId());
        record.setKnowledgeBaseId(conversation.getKnowledgeBaseId());
        record.setQuestion(request.getQuestion());
        record.setAnswer(response.getAnswer());
        record.setSources(JsonUtil.toJson(response.getSources()));
        record.setRetrievalTime(nullToZero(response.getRetrievalTime()));
        record.setGenerationTime(nullToZero(response.getGenerationTime()));
        record.setTotalTime(nullToZero(response.getTotalTime()));
        record.setTotalTokens(nullToZero(response.getTotalTokens()));
        qaRecordMapper.insert(record);

        log.info("问答完成: conversation={}, sources={}, totalTime={}ms",
                conversation.getId(), response.getSources() == null ? 0 : response.getSources().size(),
                response.getTotalTime());

        return AskVO.builder()
                .conversationId(conversation.getId())
                .userMessageId(userMsg.getId())
                .assistantMessageId(assistantMsg.getId())
                .response(response)
                .build();
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
                                int retrievalTime, int generationTime, int totalTokens) {
        Message msg = new Message();
        msg.setConversationId(conversationId);
        msg.setRole(role);
        msg.setContent(content);
        msg.setSources(sources);
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
        return MessageVO.builder()
                .id(m.getId())
                .conversationId(m.getConversationId())
                .role(m.getRole())
                .content(m.getContent())
                .sources(sources)
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
