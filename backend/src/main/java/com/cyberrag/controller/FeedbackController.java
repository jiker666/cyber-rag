package com.cyberrag.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.common.result.Result;
import com.cyberrag.entity.Feedback;
import com.cyberrag.entity.Message;
import com.cyberrag.mapper.FeedbackMapper;
import com.cyberrag.mapper.MessageMapper;
import com.cyberrag.security.AuthContext;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 用户反馈接口。
 */
@Tag(name = "用户反馈")
@RestController
@RequestMapping("/api/feedback")
@RequiredArgsConstructor
public class FeedbackController {

    private final FeedbackMapper feedbackMapper;
    private final MessageMapper messageMapper;

    @Data
    public static class FeedbackRequest {
        @NotNull(message = "消息 ID 不能为空")
        private Long messageId;
        /** 1 有用 / -1 无用 */
        @NotNull(message = "评分不能为空")
        private Integer rating;
        private String comment;
    }

    @Operation(summary = "提交反馈")
    @PostMapping
    public Result<Void> submit(@RequestBody FeedbackRequest request) {
        if (request.getRating() != 1 && request.getRating() != -1) {
            throw new BusinessException(400, "评分仅支持 1 或 -1");
        }
        Message message = messageMapper.selectById(request.getMessageId());
        if (message == null) {
            throw new BusinessException(404, "消息不存在");
        }
        // 同一用户同一消息只保留一条反馈
        Feedback existing = feedbackMapper.selectOne(new LambdaQueryWrapper<Feedback>()
                .eq(Feedback::getUserId, AuthContext.getUserId())
                .eq(Feedback::getMessageId, request.getMessageId()));
        if (existing != null) {
            existing.setRating(request.getRating());
            existing.setComment(request.getComment());
            feedbackMapper.updateById(existing);
        } else {
            Feedback feedback = new Feedback();
            feedback.setUserId(AuthContext.getUserId());
            feedback.setMessageId(request.getMessageId());
            feedback.setRating(request.getRating());
            feedback.setComment(request.getComment());
            feedbackMapper.insert(feedback);
        }
        return Result.success();
    }

    @Operation(summary = "反馈列表(管理员)")
    @GetMapping
    public Result<IPage<Feedback>> page(@RequestParam(defaultValue = "1") long page,
                                        @RequestParam(defaultValue = "10") long size) {
        if (!AuthContext.isAdmin()) {
            throw new BusinessException(403, "需要管理员权限");
        }
        return Result.success(feedbackMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<Feedback>().orderByDesc(Feedback::getCreatedAt)));
    }
}
