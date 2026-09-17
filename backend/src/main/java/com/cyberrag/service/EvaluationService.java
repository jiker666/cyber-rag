package com.cyberrag.service;

import com.cyberrag.dto.eval.EvalRunRequest;
import com.cyberrag.dto.eval.ManualScoreRequest;
import com.cyberrag.entity.EvaluationDataset;
import com.cyberrag.entity.EvaluationResult;
import com.cyberrag.entity.EvaluationTask;

import java.util.List;
import java.util.Map;

/**
 * 评测服务: 数据集 / 任务 / 人工评分 / 导出。
 */
public interface EvaluationService {

    // ---- 数据集 ----
    EvaluationDataset createDataset(String name, String description);

    void addItems(long datasetId, List<Map<String, String>> items);

    List<EvaluationDataset> listDatasets();

    List<Map<String, Object>> datasetItems(long datasetId);

    void deleteDataset(long datasetId);

    // ---- 任务 ----
    EvaluationTask runTask(EvalRunRequest request);

    List<EvaluationTask> listTasks();

    EvaluationTask taskDetail(long taskId);

    void deleteTask(long taskId);

    List<EvaluationResult> taskResults(long taskId);

    Map<String, Object> taskSummary(long taskId);

    // ---- 人工评分与导出 ----
    void submitManualScore(long resultId, ManualScoreRequest request);

    String exportCsv(long taskId);

    /** 多任务指标对比(论文实验用) */
    List<Map<String, Object>> compareTasks(List<Long> taskIds);
}
