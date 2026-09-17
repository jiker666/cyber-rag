package com.cyberrag.controller;

import com.cyberrag.common.result.Result;
import com.cyberrag.dto.eval.EvalRunRequest;
import com.cyberrag.dto.eval.ManualScoreRequest;
import com.cyberrag.entity.EvaluationDataset;
import com.cyberrag.entity.EvaluationResult;
import com.cyberrag.entity.EvaluationTask;
import com.cyberrag.security.RequireAdmin;
import com.cyberrag.service.EvaluationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * 评测模块接口: 运行实验 / 结果查看 / 人工评分 / CSV 导出 / 对比。
 */
@Tag(name = "RAG 实验")
@RestController
@RequestMapping("/api/evaluation")
@RequiredArgsConstructor
public class EvaluationController {

    private final EvaluationService evaluationService;

    // ---- 数据集 ----
    @Operation(summary = "数据集列表")
    @GetMapping("/datasets")
    public Result<List<EvaluationDataset>> datasets() {
        return Result.success(evaluationService.listDatasets());
    }

    @Operation(summary = "数据集题目")
    @GetMapping("/datasets/{id}/items")
    public Result<List<Map<String, Object>>> datasetItems(@PathVariable long id) {
        return Result.success(evaluationService.datasetItems(id));
    }

    @Operation(summary = "创建数据集")
    @RequireAdmin
    @PostMapping("/datasets")
    public Result<EvaluationDataset> createDataset(@RequestBody Map<String, String> body) {
        return Result.success(evaluationService.createDataset(
                body.getOrDefault("name", "未命名数据集"), body.get("description")));
    }

    @Operation(summary = "批量添加题目")
    @RequireAdmin
    @PostMapping("/datasets/{id}/items")
    public Result<Void> addItems(@PathVariable long id,
                                 @RequestBody List<Map<String, String>> items) {
        evaluationService.addItems(id, items);
        return Result.success();
    }

    @Operation(summary = "删除数据集")
    @RequireAdmin
    @DeleteMapping("/datasets/{id}")
    public Result<Void> deleteDataset(@PathVariable long id) {
        evaluationService.deleteDataset(id);
        return Result.success();
    }

    // ---- 任务 ----
    @Operation(summary = "评测任务列表")
    @GetMapping("/tasks")
    public Result<List<EvaluationTask>> tasks() {
        return Result.success(evaluationService.listTasks());
    }

    @Operation(summary = "发起评测任务")
    @RequireAdmin
    @PostMapping("/tasks")
    public Result<EvaluationTask> runTask(@Valid @RequestBody EvalRunRequest request) {
        return Result.success(evaluationService.runTask(request));
    }

    @Operation(summary = "任务详情与汇总指标")
    @GetMapping("/tasks/{id}/summary")
    public Result<Map<String, Object>> taskSummary(@PathVariable long id) {
        return Result.success(evaluationService.taskSummary(id));
    }

    @Operation(summary = "任务结果列表")
    @GetMapping("/tasks/{id}/results")
    public Result<List<EvaluationResult>> taskResults(@PathVariable long id) {
        return Result.success(evaluationService.taskResults(id));
    }

    @Operation(summary = "删除任务")
    @RequireAdmin
    @DeleteMapping("/tasks/{id}")
    public Result<Void> deleteTask(@PathVariable long id) {
        evaluationService.deleteTask(id);
        return Result.success();
    }

    // ---- 评分 / 导出 / 对比 ----
    @Operation(summary = "人工评分")
    @RequireAdmin
    @PutMapping("/results/{id}/manual-score")
    public Result<Void> manualScore(@PathVariable long id,
                                    @Valid @RequestBody ManualScoreRequest request) {
        evaluationService.submitManualScore(id, request);
        return Result.success();
    }

    @Operation(summary = "导出任务结果 CSV")
    @RequireAdmin
    @GetMapping("/tasks/{id}/export")
    public ResponseEntity<byte[]> exportCsv(@PathVariable long id) {
        String csv = evaluationService.exportCsv(id);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=eval_task_" + id + ".csv")
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .body(("﻿" + csv).getBytes(StandardCharsets.UTF_8)); // BOM 便于 Excel 识别 UTF-8
    }

    @Operation(summary = "多任务指标对比")
    @GetMapping("/compare")
    public Result<List<Map<String, Object>>> compare(@RequestParam String taskIds) {
        List<Long> ids = java.util.Arrays.stream(taskIds.split(","))
                .map(String::trim).filter(s -> !s.isEmpty()).map(Long::parseLong).toList();
        return Result.success(evaluationService.compareTasks(ids));
    }
}
