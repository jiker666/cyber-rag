package com.cyberrag.controller;

import com.cyberrag.common.result.Result;
import com.cyberrag.entity.RagConfig;
import com.cyberrag.integration.RagServiceClient;
import com.cyberrag.security.RequireAdmin;
import com.cyberrag.service.RagConfigService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * RAG 参数配置接口。
 */
@Tag(name = "RAG 配置")
@RestController
@RequestMapping("/api/rag-config")
@RequiredArgsConstructor
public class RagConfigController {

    private final RagConfigService ragConfigService;
    private final RagServiceClient ragClient;

    @Operation(summary = "查询 RAG 配置")
    @GetMapping
    public Result<RagConfig> get() {
        return Result.success(ragConfigService.getConfig());
    }

    @Operation(summary = "更新 RAG 配置")
    @RequireAdmin
    @PutMapping
    public Result<RagConfig> update(@RequestBody RagConfig config) {
        return Result.success(ragConfigService.update(config));
    }

    @Operation(summary = "AI 服务运行时信息(模型/向量库)")
    @GetMapping("/runtime")
    public Result<Map<String, Object>> runtime() {
        return Result.success(ragClient.runtimeConfig());
    }
}
