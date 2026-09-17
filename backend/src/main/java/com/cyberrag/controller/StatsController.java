package com.cyberrag.controller;

import com.cyberrag.common.result.Result;
import com.cyberrag.service.StatsService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 后台统计接口。
 */
@Tag(name = "统计看板")
@RestController
@RequestMapping("/api/stats")
@RequiredArgsConstructor
public class StatsController {

    private final StatsService statsService;

    @Operation(summary = "总览卡片数据")
    @GetMapping("/overview")
    public Result<Map<String, Object>> overview() {
        return Result.success(statsService.overview());
    }

    @Operation(summary = "最近 N 天问答趋势")
    @GetMapping("/qa-trend")
    public Result<List<Map<String, Object>>> qaTrend(@RequestParam(defaultValue = "7") int days) {
        return Result.success(statsService.qaTrend(Math.min(Math.max(days, 1), 30)));
    }

    @Operation(summary = "热门问题类别")
    @GetMapping("/hot-categories")
    public Result<List<Map<String, Object>>> hotCategories(@RequestParam(defaultValue = "6") int limit) {
        return Result.success(statsService.hotCategories(limit));
    }

    @Operation(summary = "知识库使用占比")
    @GetMapping("/kb-usage")
    public Result<List<Map<String, Object>>> kbUsage(@RequestParam(defaultValue = "6") int limit) {
        return Result.success(statsService.kbUsage(limit));
    }

    @Operation(summary = "最近问答记录")
    @GetMapping("/recent-qa")
    public Result<List<Map<String, Object>>> recentQa(@RequestParam(defaultValue = "10") int limit) {
        return Result.success(statsService.recentQa(limit));
    }
}
