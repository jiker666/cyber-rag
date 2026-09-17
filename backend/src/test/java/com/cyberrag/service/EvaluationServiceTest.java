package com.cyberrag.service;

import com.cyberrag.BaseTest;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.eval.EvalRunRequest;
import com.cyberrag.dto.eval.ManualScoreRequest;
import com.cyberrag.dto.rag.EvalBatchRequest;
import com.cyberrag.dto.rag.EvalBatchResponse;
import com.cyberrag.entity.EvaluationResult;
import com.cyberrag.entity.EvaluationTask;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.awaitility.Awaitility;

import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * 评测服务测试: 任务创建/执行/结果落库/人工评分/CSV 导出。
 */
class EvaluationServiceTest extends BaseTest {

    @Autowired
    private EvaluationService evaluationService;

    @BeforeEach
    void mockEvalBatch() {
        EvalBatchResponse response = new EvalBatchResponse();
        EvalBatchResponse.EvalItemResult r1 = new EvalBatchResponse.EvalItemResult();
        r1.setItemId(1L);
        r1.setQuestion("如何防御SQL注入?");
        r1.setMode("RAG_LLM");
        r1.setAnswer("[1] 使用参数化查询。");
        r1.setRetrievalTime(100);
        r1.setGenerationTime(700);
        r1.setTotalTime(800);
        r1.setPromptTokens(50);
        r1.setCompletionTokens(60);
        r1.setRetrievalHit(true);
        r1.setPrecisionAtK(1.0);
        r1.setRecallAtK(1.0);
        r1.setKeywordHitRate(1.0);
        r1.setCitationMatched(1.0);
        EvalBatchResponse.EvalItemResult r2 = new EvalBatchResponse.EvalItemResult();
        r2.setItemId(2L);
        r2.setQuestion("什么是XSS?");
        r2.setMode("RAG_LLM");
        r2.setAnswer("XSS 是跨站脚本攻击, 未知来源。");
        r2.setTotalTime(600);
        r2.setRetrievalHit(false);
        r2.setPrecisionAtK(0.0);
        r2.setRecallAtK(0.0);
        r2.setKeywordHitRate(0.0);
        r2.setCitationMatched(0.0);
        response.setResults(List.of(r1, r2));
        EvalBatchResponse.EvalMetrics metrics = new EvalBatchResponse.EvalMetrics();
        metrics.setTotal(2);
        metrics.setCompleted(2);
        metrics.setFailed(0);
        metrics.setRetrievalHitRate(0.5);
        metrics.setCitationAccuracy(0.5);
        response.setMetrics(metrics);
        when(ragServiceClient.evaluationBatch(any(EvalBatchRequest.class))).thenReturn(response);
    }

    private EvalRunRequest runRequest(String name, String mode) {
        EvalRunRequest request = new EvalRunRequest();
        request.setName(name);
        request.setMode(mode);
        request.setDatasetId(1L);
        request.setKnowledgeBaseId(1L);
        request.setTopK(5);
        return request;
    }

    @Test
    void run_rag_task_persists_results_and_metrics() {
        EvaluationTask task = evaluationService.runTask(runRequest("RAG实验", "RAG_LLM"));
        assertNotNull(task.getId());
        assertEquals("RAG_LLM", task.getMode());

        Awaitility.await().atMost(5, TimeUnit.SECONDS).untilAsserted(() -> {
            EvaluationTask current = evaluationService.taskDetail(task.getId());
            assertEquals("COMPLETED", current.getStatus());
            assertEquals(2, current.getTotal());
            assertEquals(2, current.getCompleted());
            assertNotNull(current.getMetrics());
        });
        List<EvaluationResult> results = evaluationService.taskResults(task.getId());
        assertEquals(2, results.size());
        assertEquals(1, results.get(0).getRetrievalHit());
        assertEquals(1.0, results.get(0).getPrecisionAtK().doubleValue());
        assertEquals(0, results.get(1).getRetrievalHit());
    }

    @Test
    void llm_only_mode_rejects_missing_dataset() {
        EvalRunRequest request = runRequest("LLM实验", "LLM_ONLY");
        request.setDatasetId(999L);
        assertThrows(BusinessException.class, () -> evaluationService.runTask(request));
    }

    @Test
    void rag_mode_requires_knowledge_base() {
        EvalRunRequest request = runRequest("无知识库", "RAG_LLM");
        request.setKnowledgeBaseId(null);
        assertThrows(BusinessException.class, () -> evaluationService.runTask(request));
    }

    @Test
    void manual_score_updates_result() {
        EvaluationTask task = evaluationService.runTask(runRequest("人工评分实验", "RAG_LLM"));
        Awaitility.await().atMost(5, TimeUnit.SECONDS).until(() ->
                !evaluationService.taskResults(task.getId()).isEmpty());
        EvaluationResult result = evaluationService.taskResults(task.getId()).get(0);

        ManualScoreRequest score = new ManualScoreRequest();
        score.setCorrectness(5);
        score.setRelevance(4);
        score.setCompleteness(3);
        score.setHallucination(false);
        score.setComment("回答准确");
        evaluationService.submitManualScore(result.getId(), score);

        Map<String, Object> summary = evaluationService.taskSummary(task.getId());
        assertNotNull(summary.get("metrics"));
        @SuppressWarnings("unchecked")
        Map<String, Object> manual = (Map<String, Object>) summary.get("manualMetrics");
        assertEquals(5.0, manual.get("avgCorrectness"));
        assertEquals(0.0, manual.get("hallucinationRate"));
    }

    @Test
    void export_csv_contains_headers_and_rows() {
        EvaluationTask task = evaluationService.runTask(runRequest("导出实验", "RAG_LLM"));
        Awaitility.await().atMost(5, TimeUnit.SECONDS).until(() ->
                "COMPLETED".equals(evaluationService.taskDetail(task.getId()).getStatus()));
        String csv = evaluationService.exportCsv(task.getId());
        assertTrue(csv.contains("taskId,taskName,mode,itemId,question"));
        assertTrue(csv.contains("如何防御SQL注入?"));
    }

    @Test
    void compare_tasks_returns_metrics_rows() {
        EvaluationTask a = evaluationService.runTask(runRequest("对比A", "LLM_ONLY"));
        EvaluationTask b = evaluationService.runTask(runRequest("对比B", "RAG_LLM"));
        Awaitility.await().atMost(5, TimeUnit.SECONDS).until(() ->
                "COMPLETED".equals(evaluationService.taskDetail(a.getId()).getStatus())
                        && "COMPLETED".equals(evaluationService.taskDetail(b.getId()).getStatus()));
        List<Map<String, Object>> comparison = evaluationService.compareTasks(List.of(a.getId(), b.getId()));
        assertEquals(2, comparison.size());
        assertEquals("LLM_ONLY", comparison.get(0).get("mode"));
        assertEquals("RAG_LLM", comparison.get(1).get("mode"));
    }
}
