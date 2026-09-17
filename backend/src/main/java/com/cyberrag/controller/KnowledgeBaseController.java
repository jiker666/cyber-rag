package com.cyberrag.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.cyberrag.common.result.Result;
import com.cyberrag.dto.kb.KbUpsertRequest;
import com.cyberrag.entity.KnowledgeBase;
import com.cyberrag.security.RequireAdmin;
import com.cyberrag.service.KnowledgeBaseService;
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

import java.util.List;

/**
 * 知识库接口: 普通用户可读, 管理员可写。
 */
@Tag(name = "知识库")
@RestController
@RequestMapping("/api/kb")
@RequiredArgsConstructor
public class KnowledgeBaseController {

    private final KnowledgeBaseService kbService;

    @Operation(summary = "知识库分页列表")
    @GetMapping
    public Result<IPage<KnowledgeBase>> page(@RequestParam(defaultValue = "1") long page,
                                             @RequestParam(defaultValue = "10") long size,
                                             @RequestParam(required = false) String keyword,
                                             @RequestParam(required = false) String category) {
        return Result.success(kbService.page(page, size, keyword, category));
    }

    @Operation(summary = "可用知识库列表(问答选择用)")
    @GetMapping("/enabled")
    public Result<List<KnowledgeBase>> listEnabled() {
        return Result.success(kbService.listEnabled());
    }

    @Operation(summary = "知识库详情")
    @GetMapping("/{id}")
    public Result<KnowledgeBase> detail(@PathVariable long id) {
        return Result.success(kbService.getById(id));
    }

    @Operation(summary = "同步向量库统计")
    @PostMapping("/{id}/refresh")
    public Result<KnowledgeBase> refresh(@PathVariable long id) {
        return Result.success(kbService.refreshStats(id));
    }

    @Operation(summary = "创建知识库")
    @RequireAdmin
    @PostMapping
    public Result<KnowledgeBase> create(@Valid @RequestBody KbUpsertRequest request) {
        return Result.success(kbService.create(request));
    }

    @Operation(summary = "更新知识库")
    @RequireAdmin
    @PutMapping("/{id}")
    public Result<KnowledgeBase> update(@PathVariable long id,
                                        @Valid @RequestBody KbUpsertRequest request) {
        return Result.success(kbService.update(id, request));
    }

    @Operation(summary = "删除知识库")
    @RequireAdmin
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable long id) {
        kbService.delete(id);
        return Result.success();
    }
}
