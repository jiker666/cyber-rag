package com.cyberrag.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.cyberrag.common.result.Result;
import com.cyberrag.entity.Document;
import com.cyberrag.security.RequireAdmin;
import com.cyberrag.service.DocumentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文档接口: 上传/重新向量化为管理员操作, 列表所有用户可见。
 */
@Tag(name = "文档管理")
@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    @Operation(summary = "文档分页列表")
    @GetMapping
    public Result<IPage<Document>> page(@RequestParam(defaultValue = "1") long page,
                                        @RequestParam(defaultValue = "10") long size,
                                        @RequestParam(defaultValue = "0") long knowledgeBaseId,
                                        @RequestParam(required = false) String keyword,
                                        @RequestParam(required = false) String status) {
        return Result.success(documentService.page(page, size, knowledgeBaseId, keyword, status));
    }

    @Operation(summary = "上传文档(pdf/txt/md/docx)")
    @RequireAdmin
    @PostMapping("/upload")
    public Result<Document> upload(@RequestParam("file") MultipartFile file,
                                   @RequestParam("knowledgeBaseId") long knowledgeBaseId) {
        return Result.success(documentService.upload(file, knowledgeBaseId));
    }

    @Operation(summary = "重新向量化")
    @RequireAdmin
    @PostMapping("/{id}/reingest")
    public Result<Void> reingest(@PathVariable long id) {
        documentService.reingest(id);
        return Result.success();
    }

    @Operation(summary = "删除文档")
    @RequireAdmin
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable long id) {
        documentService.deleteDocument(id);
        return Result.success();
    }
}
