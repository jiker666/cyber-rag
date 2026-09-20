package com.cyberrag.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.common.result.Result;
import com.cyberrag.dto.chat.AskRequest;
import com.cyberrag.entity.Conversation;
import com.cyberrag.mapper.ConversationMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.ChatService;
import com.cyberrag.vo.AskVO;
import com.cyberrag.vo.MessageVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;

/**
 * 会话与问答接口。
 */
@Tag(name = "智能问答")
@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;
    private final ConversationMapper conversationMapper;

    @Operation(summary = "提问(RAG 增强问答)")
    @PostMapping("/ask")
    public Result<AskVO> ask(@Valid @RequestBody AskRequest request) {
        return Result.success(chatService.ask(request));
    }

    @Operation(summary = "提问(SSE 流式回答)", description = "逐 token 推送: start → analysis → retrieval → delta×N → done")
    @PostMapping(value = "/ask/stream", produces = org.springframework.http.MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter askStream(@Valid @RequestBody AskRequest request) {
        return chatService.streamAsk(request);
    }

    @Operation(summary = "重新生成")
    @PostMapping("/conversations/{id}/regenerate")
    public Result<AskVO> regenerate(@PathVariable long id) {
        return Result.success(chatService.regenerate(id));
    }

    @Operation(summary = "会话消息列表")
    @GetMapping("/conversations/{id}/messages")
    public Result<List<MessageVO>> messages(@PathVariable long id) {
        return Result.success(chatService.listMessages(id));
    }

    @Operation(summary = "清空会话消息")
    @DeleteMapping("/conversations/{id}/messages")
    public Result<Void> clearMessages(@PathVariable long id) {
        chatService.clearMessages(id);
        return Result.success();
    }

    @Operation(summary = "我的会话列表")
    @GetMapping("/conversations")
    public Result<IPage<Conversation>> conversations(@RequestParam(defaultValue = "1") long page,
                                                     @RequestParam(defaultValue = "20") long size) {
        return Result.success(conversationMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getUserId, AuthContext.getUserId())
                        .orderByDesc(Conversation::getLastMessageAt)));
    }

    @Operation(summary = "重命名会话")
    @PutMapping("/conversations/{id}/title")
    public Result<Void> rename(@PathVariable long id, @RequestBody Map<String, String> body) {
        Conversation conversation = ownedConversation(id);
        String title = body.getOrDefault("title", "").trim();
        if (title.isEmpty() || title.length() > 100) {
            throw new BusinessException(400, "标题长度 1-100 字符");
        }
        conversation.setTitle(title);
        conversationMapper.updateById(conversation);
        return Result.success();
    }

    @Operation(summary = "删除会话")
    @DeleteMapping("/conversations/{id}")
    public Result<Void> deleteConversation(@PathVariable long id) {
        Conversation conversation = ownedConversation(id);
        conversationMapper.deleteById(conversation.getId());
        return Result.success();
    }

    private Conversation ownedConversation(long id) {
        Conversation conversation = conversationMapper.selectById(id);
        if (conversation == null) {
            throw new BusinessException(404, "会话不存在");
        }
        boolean admin = AuthContext.isAdmin();
        if (!admin && !conversation.getUserId().equals(AuthContext.getUserId())) {
            throw new BusinessException(403, "无权访问该会话");
        }
        return conversation;
    }
}
