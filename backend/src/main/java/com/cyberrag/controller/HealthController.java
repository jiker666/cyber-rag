package com.cyberrag.controller;

import com.cyberrag.common.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 健康检查端点(免鉴权): 供 docker healthcheck 与部署冒烟测试使用。
 */
@Tag(name = "系统")
@RestController
@RequestMapping("/api/health")
public class HealthController {

    @Operation(summary = "服务健康检查")
    @GetMapping
    public Result<Map<String, String>> health() {
        return Result.success(Map.of("status", "UP"));
    }
}
