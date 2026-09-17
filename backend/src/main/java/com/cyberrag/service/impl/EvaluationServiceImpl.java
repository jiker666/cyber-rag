package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.cyberrag.common.constants.Constants;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.eval.EvalRunRequest;
import com.cyberrag.dto.eval.ManualScoreRequest;
import com.cyberrag.dto.rag.EvalBatchRequest;
import com.cyberrag.dto.rag.EvalBatchResponse;
import com.cyberrag.entity.EvaluationDataset;
import com.cyberrag.entity.EvaluationItem;
import com.cyberrag.entity.EvaluationResult;
import com.cyberrag.entity.EvaluationTask;
import com.cyberrag.entity.RagConfig;
import com.cyberrag.integration.RagServiceClient;
import com.cyberrag.mapper.EvaluationDatasetMapper;
import com.cyberrag.mapper.EvaluationItemMapper;
import com.cyberrag.mapper.EvaluationResultMapper;
import com.cyberrag.mapper.EvaluationTaskMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.EvaluationService;
import com.cyberrag.service.RagConfigService;
import com.cyberrag.util.JsonUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 评测服务实现。
 *
 * 论文实验链路: 同一数据集分别以 LLM_ONLY 与 RAG_LLM 模式真实运行,
 * 结果逐条落库; 汇总指标由 Python 服务计算, 人工评分指标在人工打分后由本服务重新汇总。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EvaluationServiceImpl implements EvaluationService {

    private final EvaluationDatasetMapper datasetMapper;
    private final EvaluationItemMapper itemMapper;
    private final EvaluationTaskMapper taskMapper;
    private final EvaluationResultMapper resultMapper;
    private final RagServiceClient ragClient;
    private final RagConfigService ragConfigService;
    private final ExecutorService evalExecutor = Executors.newFixedThreadPool(1, r -> {
        Thread t = new Thread(r, "eval-runner");
        t.setDaemon(true);
        return t;
    });

    // =====================================================================
    // 数据集
    // =====================================================================
    @Override
    public EvaluationDataset createDataset(String name, String description) {
        EvaluationDataset dataset = new EvaluationDataset();
        dataset.setName(name);
        dataset.setDescription(description);
        dataset.setItemCount(0);
        dataset.setCreatedBy(AuthContext.getUserId());
        datasetMapper.insert(dataset);
        return dataset;
    }

    @Override
    public void addItems(long datasetId, List<Map<String, String>> items) {
        EvaluationDataset dataset = datasetMapper.selectById(datasetId);
        if (dataset == null) {
            throw new BusinessException(404, "数据集不存在");
        }
        int added = 0;
        for (Map<String, String> raw : items) {
            String question = raw.get("question");
            if (question == null || question.isBlank()) {
                continue;
            }
            EvaluationItem item = new EvaluationItem();
            item.setDatasetId(datasetId);
            item.setQuestion(question.trim());
            item.setReferenceAnswer(raw.get("referenceAnswer"));
            item.setExpectedKeywords(raw.get("expectedKeywords"));
            item.setExpectedSource(raw.get("expectedSource"));
            item.setCategory(raw.get("category"));
            itemMapper.insert(item);
            added++;
        }
        dataset.setItemCount((dataset.getItemCount() == null ? 0 : dataset.getItemCount()) + added);
        datasetMapper.updateById(dataset);
    }

    @Override
    public List<EvaluationDataset> listDatasets() {
        return datasetMapper.selectList(new LambdaQueryWrapper<EvaluationDataset>()
                .orderByDesc(EvaluationDataset::getCreatedAt));
    }

    @Override
    public List<Map<String, Object>> datasetItems(long datasetId) {
        List<EvaluationItem> items = itemMapper.selectList(new LambdaQueryWrapper<EvaluationItem>()
                .eq(EvaluationItem::getDatasetId, datasetId)
                .orderByAsc(EvaluationItem::getId));
        return items.stream().map(i -> {
            Map<String, Object> m = new HashMap<>();
            m.put("id", i.getId());
            m.put("question", i.getQuestion());
            m.put("referenceAnswer", i.getReferenceAnswer());
            m.put("expectedKeywords", i.getExpectedKeywords());
            m.put("expectedSource", i.getExpectedSource());
            m.put("category", i.getCategory());
            return m;
        }).toList();
    }

    @Override
    public void deleteDataset(long datasetId) {
        Long used = taskMapper.selectCount(new LambdaQueryWrapper<EvaluationTask>()
                .eq(EvaluationTask::getDatasetId, datasetId));
        if (used > 0) {
            throw new BusinessException(400, "该数据集已关联评测任务, 无法删除");
        }
        itemMapper.delete(new LambdaQueryWrapper<EvaluationItem>()
                .eq(EvaluationItem::getDatasetId, datasetId));
        datasetMapper.deleteById(datasetId);
    }

    // =====================================================================
    // 任务执行
    // =====================================================================
    @Override
    public EvaluationTask runTask(EvalRunRequest request) {
        if (!Constants.MODE_LLM_ONLY.equals(request.getMode())
                && !Constants.MODE_RAG_LLM.equals(request.getMode())) {
            throw new BusinessException(400, "模式仅支持 LLM_ONLY 或 RAG_LLM");
        }
        EvaluationDataset dataset = datasetMapper.selectById(request.getDatasetId());
        if (dataset == null) {
            throw new BusinessException(404, "数据集不存在");
        }
        if (Constants.MODE_RAG_LLM.equals(request.getMode()) && request.getKnowledgeBaseId() == null) {
            throw new BusinessException(400, "RAG 模式必须选择知识库");
        }
        RagConfig config = ragConfigService.getConfig();

        EvaluationTask task = new EvaluationTask();
        task.setName(request.getName());
        task.setMode(request.getMode());
        task.setKnowledgeBaseId(request.getKnowledgeBaseId());
        task.setDatasetId(request.getDatasetId());
        task.setTopK(request.getTopK() != null ? request.getTopK() : config.getTopK());
        task.setChunkSize(request.getChunkSize());
        task.setChunkOverlap(request.getChunkOverlap());
        task.setTemperature(request.getTemperature() != null
                ? BigDecimal.valueOf(request.getTemperature()) : config.getTemperature());
        task.setEnableReranker(Boolean.TRUE.equals(request.getEnableReranker()) ? 1 : 0);
        task.setRetrievalStrategy(request.getRetrievalStrategy() != null
                ? request.getRetrievalStrategy() : "vector");
        task.setTotal(0);
        task.setCompleted(0);
        task.setFailed(0);
        task.setStatus(Constants.TASK_PENDING);
        task.setCreatedBy(AuthContext.getUserId());
        taskMapper.insert(task);
        log.info("创建评测任务: id={}, name={}, mode={}", task.getId(), task.getName(), task.getMode());

        long taskId = task.getId();
        evalExecutor.submit(() -> {
            try {
                executeTask(taskId);
            } catch (Exception e) {
                log.error("评测任务执行异常: taskId={}", taskId, e);
                EvaluationTask t = taskMapper.selectById(taskId);
                if (t != null) {
                    t.setStatus(Constants.TASK_FAILED);
                    t.setErrorMsg(truncateError(e.getMessage()));
                    taskMapper.updateById(t);
                }
            }
        });
        return task;
    }

    private void executeTask(long taskId) {
        EvaluationTask task = taskMapper.selectById(taskId);
        if (task == null) {
            return;
        }
        task.setStatus(Constants.TASK_RUNNING);
        taskMapper.updateById(task);
        try {
            List<EvaluationItem> items = itemMapper.selectList(new LambdaQueryWrapper<EvaluationItem>()
                    .eq(EvaluationItem::getDatasetId, task.getDatasetId())
                    .orderByAsc(EvaluationItem::getId));
            if (items.isEmpty()) {
                throw new BusinessException(400, "数据集没有题目");
            }
            task.setTotal(items.size());
            taskMapper.updateById(task);

            EvalBatchRequest batchRequest = new EvalBatchRequest();
            batchRequest.setMode(task.getMode());
            batchRequest.setKnowledgeBaseId(task.getKnowledgeBaseId());
            EvalBatchRequest.EvalParams params = new EvalBatchRequest.EvalParams();
            params.setTopK(task.getTopK());
            params.setTemperature(task.getTemperature() != null ? task.getTemperature().doubleValue() : null);
            params.setEnableReranker(task.getEnableReranker() != null && task.getEnableReranker() == 1);
            params.setRetrievalStrategy(task.getRetrievalStrategy() != null
                    ? task.getRetrievalStrategy() : "vector");
            batchRequest.setParams(params);
            batchRequest.setItems(items.stream().map(i -> {
                EvalBatchRequest.EvalItem item = new EvalBatchRequest.EvalItem();
                item.setItemId(i.getId());
                item.setQuestion(i.getQuestion());
                item.setReferenceAnswer(i.getReferenceAnswer());
                item.setExpectedKeywords(i.getExpectedKeywords());
                item.setExpectedSource(i.getExpectedSource());
                return item;
            }).toList());

            log.info("评测任务开始执行: taskId={}, items={}", taskId, items.size());
            EvalBatchResponse response = ragClient.evaluationBatch(batchRequest);

            // 逐题落库
            int completed = 0;
            for (EvalBatchResponse.EvalItemResult r : response.getResults()) {
                EvaluationResult result = new EvaluationResult();
                result.setTaskId(taskId);
                result.setItemId(r.getItemId());
                result.setQuestion(r.getQuestion());
                result.setMode(task.getMode());
                result.setAnswer(r.getAnswer());
                result.setSources(JsonUtil.toJson(r.getSources()));
                result.setRetrievalTime(r.getRetrievalTime() == null ? 0 : r.getRetrievalTime());
                result.setGenerationTime(r.getGenerationTime() == null ? 0 : r.getGenerationTime());
                result.setTotalTime(r.getTotalTime() == null ? 0 : r.getTotalTime());
                result.setPromptTokens(r.getPromptTokens() == null ? 0 : r.getPromptTokens());
                result.setCompletionTokens(r.getCompletionTokens() == null ? 0 : r.getCompletionTokens());
                if (r.getRetrievalHit() != null) {
                    result.setRetrievalHit(r.getRetrievalHit() ? 1 : 0);
                }
                result.setPrecisionAtK(toBigDecimal(r.getPrecisionAtK()));
                result.setRecallAtK(toBigDecimal(r.getRecallAtK()));
                result.setMrr(toBigDecimal(r.getMrr()));
                result.setKeywordHitRate(toBigDecimal(r.getKeywordHitRate()));
                if (r.getCitationMatched() != null) {
                    // 引用准确率>0 视为引用匹配成功(0-1 连续值)
                    result.setCitationMatched(r.getCitationMatched() > 0.5 ? 1 : 0);
                }
                result.setManualCorrectness(0);
                result.setManualRelevance(0);
                result.setManualCompleteness(0);
                result.setManualHallucination(0);
                result.setManualScored(0);
                if (r.getError() != null) {
                    result.setError(r.getError().substring(0, Math.min(500, r.getError().length())));
                }
                resultMapper.insert(result);
                if (r.getError() == null) {
                    completed++;
                }
            }
            task.setCompleted(completed);
            task.setFailed(items.size() - completed);
            task.setMetrics(JsonUtil.toJson(response.getMetrics()));
            task.setStatus(Constants.TASK_COMPLETED);
            taskMapper.updateById(task);
            log.info("评测任务完成: taskId={}, completed={}, failed={}", taskId, completed, task.getFailed());
        } catch (Exception e) {
            task = taskMapper.selectById(taskId);
            if (task != null) {
                task.setStatus(Constants.TASK_FAILED);
                task.setErrorMsg(truncateError(e.getMessage()));
                taskMapper.updateById(task);
            }
            log.error("评测任务失败: taskId={}", taskId, e);
        }
    }

    /** error_msg 列为 VARCHAR(1000), 防止超长异常信息导致更新失败。 */
    private String truncateError(String msg) {
        if (msg == null) {
            return "未知错误";
        }
        return msg.substring(0, Math.min(1000, msg.length()));
    }

    // =====================================================================
    // 查询 / 评分 / 导出 / 对比
    // =====================================================================
    @Override
    public List<EvaluationTask> listTasks() {
        return taskMapper.selectList(new LambdaQueryWrapper<EvaluationTask>()
                .orderByDesc(EvaluationTask::getCreatedAt));
    }

    @Override
    public EvaluationTask taskDetail(long taskId) {
        EvaluationTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(404, "任务不存在");
        }
        return task;
    }

    @Override
    public void deleteTask(long taskId) {
        taskMapper.deleteById(taskId);
        resultMapper.delete(new LambdaQueryWrapper<EvaluationResult>()
                .eq(EvaluationResult::getTaskId, taskId));
    }

    @Override
    public List<EvaluationResult> taskResults(long taskId) {
        return resultMapper.selectList(new LambdaQueryWrapper<EvaluationResult>()
                .eq(EvaluationResult::getTaskId, taskId)
                .orderByAsc(EvaluationResult::getId));
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> taskSummary(long taskId) {
        EvaluationTask task = taskDetail(taskId);
        Map<String, Object> summary = new HashMap<>();
        summary.put("task", task);
        Map<String, Object> metrics = null;
        if (task.getMetrics() != null) {
            metrics = JsonUtil.fromJson(task.getMetrics(), Map.class);
        }
        summary.put("metrics", metrics);
        // 人工评分汇总(仅统计已评分结果)
        List<EvaluationResult> results = taskResults(taskId);
        List<EvaluationResult> scored = results.stream()
                .filter(r -> r.getManualScored() != null && r.getManualScored() == 1).toList();
        if (!scored.isEmpty()) {
            summary.put("manualMetrics", Map.of(
                    "scoredCount", scored.size(),
                    "avgCorrectness", avgInt(scored.stream().mapToInt(EvaluationResult::getManualCorrectness)),
                    "avgRelevance", avgInt(scored.stream().mapToInt(EvaluationResult::getManualRelevance)),
                    "avgCompleteness", avgInt(scored.stream().mapToInt(EvaluationResult::getManualCompleteness)),
                    "hallucinationRate", scored.stream()
                            .filter(r -> r.getManualHallucination() != null && r.getManualHallucination() == 1)
                            .count() / (double) scored.size()));
        }
        return summary;
    }

    @Override
    public void submitManualScore(long resultId, ManualScoreRequest request) {
        EvaluationResult result = resultMapper.selectById(resultId);
        if (result == null) {
            throw new BusinessException(404, "评测结果不存在");
        }
        result.setManualCorrectness(request.getCorrectness());
        result.setManualRelevance(request.getRelevance());
        result.setManualCompleteness(request.getCompleteness());
        result.setManualHallucination(request.getHallucination() ? 1 : 0);
        result.setManualComment(request.getComment());
        result.setManualScored(1);
        resultMapper.updateById(result);
    }

    @Override
    public String exportCsv(long taskId) {
        EvaluationTask task = taskDetail(taskId);
        List<EvaluationResult> results = taskResults(taskId);
        StringBuilder sb = new StringBuilder();
        sb.append("taskId,taskName,mode,itemId,question,answer,retrievalTimeMs,generationTimeMs,totalTimeMs,")
          .append("promptTokens,completionTokens,retrievalHit,precisionAtK,recallAtK,mrr,keywordHitRate,citationMatched,")
          .append("manualCorrectness,manualRelevance,manualCompleteness,manualHallucination,error\n");
        for (EvaluationResult r : results) {
            sb.append(taskId).append(',')
              .append(csv(task.getName())).append(',')
              .append(csv(r.getMode())).append(',')
              .append(r.getItemId()).append(',')
              .append(csv(r.getQuestion())).append(',')
              .append(csv(r.getAnswer())).append(',')
              .append(r.getRetrievalTime()).append(',')
              .append(r.getGenerationTime()).append(',')
              .append(r.getTotalTime()).append(',')
              .append(r.getPromptTokens()).append(',')
              .append(r.getCompletionTokens()).append(',')
              .append(r.getRetrievalHit() == null ? "" : r.getRetrievalHit()).append(',')
              .append(r.getPrecisionAtK() == null ? "" : r.getPrecisionAtK()).append(',')
              .append(r.getRecallAtK() == null ? "" : r.getRecallAtK()).append(',')
              .append(r.getMrr() == null ? "" : r.getMrr()).append(',')
              .append(r.getKeywordHitRate() == null ? "" : r.getKeywordHitRate()).append(',')
              .append(r.getCitationMatched() == null ? "" : r.getCitationMatched()).append(',')
              .append(r.getManualCorrectness()).append(',')
              .append(r.getManualRelevance()).append(',')
              .append(r.getManualCompleteness()).append(',')
              .append(r.getManualHallucination()).append('\n');
        }
        return sb.toString();
    }

    @Override
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> compareTasks(List<Long> taskIds) {
        List<Map<String, Object>> comparison = new ArrayList<>();
        for (Long id : taskIds) {
            EvaluationTask task = taskMapper.selectById(id);
            if (task == null) {
                continue;
            }
            Map<String, Object> row = new HashMap<>();
            row.put("taskId", task.getId());
            row.put("name", task.getName());
            row.put("mode", task.getMode());
            row.put("topK", task.getTopK());
            row.put("enableReranker", task.getEnableReranker());
            row.put("retrievalStrategy", task.getRetrievalStrategy());
            row.put("chunkSize", task.getChunkSize());
            row.put("status", task.getStatus());
            Map<String, Object> metrics = task.getMetrics() != null
                    ? JsonUtil.fromJson(task.getMetrics(), Map.class) : new HashMap<>();
            row.put("metrics", metrics);
            comparison.add(row);
        }
        return comparison;
    }

    // ------------------------------------------------------------------
    private static String csv(String value) {
        if (value == null) {
            return "";
        }
        String v = value.replace("\r", " ").replace("\n", " ");
        if (v.contains(",") || v.contains("\"")) {
            v = '"' + v.replace("\"", "\"\"") + '"';
        }
        return v;
    }

    private static BigDecimal toBigDecimal(Double value) {
        return value == null ? null : BigDecimal.valueOf(value).setScale(4, RoundingMode.HALF_UP);
    }

    private static double avgInt(java.util.stream.IntStream stream) {
        return stream.average().orElse(0);
    }
}
