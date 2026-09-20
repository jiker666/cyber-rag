package com.cyberrag.integration;

import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.config.AppProperties;
import com.cyberrag.util.JsonUtil;
import com.cyberrag.dto.rag.ChatRequest;
import com.cyberrag.dto.rag.ChatResponse;
import com.cyberrag.dto.rag.EvalBatchRequest;
import com.cyberrag.dto.rag.EvalBatchResponse;
import com.cyberrag.dto.rag.IngestResult;
import com.cyberrag.dto.rag.LlmOnlyRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.DefaultUriBuilderFactory;

import java.io.File;
import java.util.Map;
import java.util.Objects;

/**
 * Python RAG 服务客户端: 文档入库 / 问答 / 检索 / 评测。
 */
@Slf4j
@Component
public class RagServiceClient {

    private final AppProperties properties;
    private final RestTemplate restTemplate;

    public RagServiceClient(AppProperties properties) {
        this.properties = properties;
        // 连接超时 10s: 快速暴露 rag-service 未启动; 读超时不设上限——
        // 评测批量为长阻塞调用(15 题 × 数十秒生成), 固定读超时会在实验中途截断任务
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        this.restTemplate = new RestTemplate(factory);
        var uriFactory = new DefaultUriBuilderFactory();
        uriFactory.setEncodingMode(DefaultUriBuilderFactory.EncodingMode.NONE);
        this.restTemplate.setUriTemplateHandler(uriFactory);
    }

    private String url(String path) {
        return properties.getRag().getServiceUrl() + path;
    }

    private HttpHeaders jsonHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (!properties.getRag().getInternalToken().isEmpty()) {
            headers.set("X-Internal-Token", properties.getRag().getInternalToken());
        }
        return headers;
    }

    /** 统一请求 + 异常转换 */
    @SuppressWarnings("unchecked")
    private Map<String, Object> doRequest(String path, HttpMethod method, Object body, MultiValueMap<String, ?> formData) {
        try {
            HttpEntity<?> entity;
            if (formData != null) {
                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.MULTIPART_FORM_DATA);
                if (!properties.getRag().getInternalToken().isEmpty()) {
                    headers.set("X-Internal-Token", properties.getRag().getInternalToken());
                }
                entity = new HttpEntity<>(formData, headers);
            } else {
                entity = new HttpEntity<>(body, jsonHeaders());
            }
            ResponseEntity<Map<String, Object>> resp =
                    restTemplate.exchange(url(path), method, entity,
                            new ParameterizedTypeReference<>() {
                            });
            return resp.getBody();
        } catch (ResourceAccessException e) {
            log.error("RAG 服务不可达: {}", path);
            throw new BusinessException(503, "AI 服务不可用, 请确认 rag-service 已启动");
        } catch (RestClientResponseException e) {
            String msg = e.getResponseBodyAsString();
            log.warn("RAG 服务返回错误: path={}, status={}, body={}", path, e.getStatusCode().value(), msg);
            throw new BusinessException(e.getStatusCode().value(), "AI 服务错误: " + msg);
        }
    }

    // ------------------------------------------------------------------
    // 文档入库
    // ------------------------------------------------------------------

    public IngestResult ingestFile(File file, String filename, long knowledgeBaseId, long documentId,
                                   Integer chunkSize, Integer chunkOverlap) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new FileSystemResource(file));
        // 显式传递原始文件名: multipart 文件名是服务端随机存储名, 不适合作为引用来源展示
        if (filename != null && !filename.isBlank()) {
            form.add("filename", filename);
        }
        form.add("knowledge_base_id", knowledgeBaseId);
        form.add("document_id", documentId);
        if (chunkSize != null) form.add("chunk_size", chunkSize);
        if (chunkOverlap != null) form.add("chunk_overlap", chunkOverlap);
        Map<String, Object> body = doRequest("/api/ingest/file", HttpMethod.POST, null, form);
        return parse(body, IngestResult.class);
    }

    public IngestResult ingestText(String text, String documentName, String source,
                                   long knowledgeBaseId, long documentId,
                                   Integer chunkSize, Integer chunkOverlap) {
        Map<String, Object> payload = Map.of(
                "knowledge_base_id", knowledgeBaseId,
                "document_id", documentId,
                "document_name", documentName,
                "source", source,
                "text", text,
                "chunk_size", Objects.requireNonNullElse(chunkSize, 512),
                "chunk_overlap", Objects.requireNonNullElse(chunkOverlap, 100)
        );
        Map<String, Object> body = doRequest("/api/ingest/text", HttpMethod.POST, payload, null);
        return parse(body, IngestResult.class);
    }

    public void deleteDocumentVectors(long knowledgeBaseId, long documentId) {
        doRequest("/api/ingest/document/" + knowledgeBaseId + "/" + documentId,
                HttpMethod.DELETE, null, null);
    }

    public void deleteCollection(long knowledgeBaseId) {
        doRequest("/api/ingest/collection/" + knowledgeBaseId, HttpMethod.DELETE, null, null);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> ingestStats(long knowledgeBaseId) {
        Map<String, Object> body = doRequest("/api/ingest/stats/" + knowledgeBaseId,
                HttpMethod.GET, null, null);
        return (Map<String, Object>) body.get("data");
    }

    // ------------------------------------------------------------------
    // 问答
    // ------------------------------------------------------------------

    public ChatResponse chatQuery(ChatRequest request) {
        Map<String, Object> body = doRequest("/api/chat/query", HttpMethod.POST, request, null);
        return parse(body, ChatResponse.class);
    }

    /**
     * 流式问答: 转发 rag-service 的 SSE 事件流(analysis/retrieval/delta/done)。
     *
     * 阻塞式逐行读取(调用方应在独立线程执行), 每解析到一个事件回调 onEvent。
     * JDK HttpClient 直连, 不走 RestTemplate(SseEmitter 场景需要边收边推)。
     */
    public void chatQueryStream(ChatRequest request, java.util.function.Consumer<Map<String, Object>> onEvent) {
        java.net.http.HttpRequest.Builder builder = java.net.http.HttpRequest.newBuilder()
                .uri(java.net.URI.create(url("/api/chat/stream")))
                .timeout(java.time.Duration.ofSeconds(30))
                .header("Content-Type", "application/json")
                .POST(java.net.http.HttpRequest.BodyPublishers.ofString(JsonUtil.toJson(request)));
        if (!properties.getRag().getInternalToken().isEmpty()) {
            builder.header("X-Internal-Token", properties.getRag().getInternalToken());
        }
        java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                .connectTimeout(java.time.Duration.ofSeconds(10))
                // 强制 HTTP/1.1: 默认 HTTP/2 会先发 h2c 升级请求(Connection: Upgrade),
                // uvicorn/h11 对携带升级头的 POST 不读请求体, 导致 rag-service 报 422 body missing
                .version(java.net.http.HttpClient.Version.HTTP_1_1)
                .build();
        try {
            java.net.http.HttpResponse<java.io.InputStream> resp =
                    client.send(builder.build(), java.net.http.HttpResponse.BodyHandlers.ofInputStream());
            if (resp.statusCode() != 200) {
                String body = new String(resp.body().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
                throw new BusinessException(resp.statusCode(), "AI 服务错误: " + body.substring(0, Math.min(body.length(), 300)));
            }
            try (java.io.BufferedReader reader = new java.io.BufferedReader(
                    new java.io.InputStreamReader(resp.body(), java.nio.charset.StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    String payload = ssePayload(line);
                    if (payload == null || payload.isEmpty()) {
                        continue;
                    }
                    try {
                        onEvent.accept(com.cyberrag.util.JsonUtil.fromJson(payload,
                                new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
                                }));
                    } catch (Exception parseEx) {
                        log.warn("SSE 事件解析失败: {}", payload.substring(0, Math.min(80, payload.length())));
                    }
                }
            }
        } catch (BusinessException e) {
            throw e;
        } catch (java.io.IOException | InterruptedException e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            log.error("RAG 流式服务调用失败: {}", e.getMessage());
            throw new BusinessException(503, "AI 流式服务不可用: " + e.getMessage());
        }
    }

    /** SSE 行 → JSON 负载(非 data 行返回 null) */
    private static String ssePayload(String line) {
        if (line.startsWith("data: ")) {
            return line.substring("data: ".length()).trim();
        }
        if (line.startsWith("data:")) {
            return line.substring("data:".length()).trim();
        }
        return null;
    }

    public ChatResponse llmOnly(LlmOnlyRequest request) {
        Map<String, Object> body = doRequest("/api/chat/llm-only", HttpMethod.POST, request, null);
        return parse(body, ChatResponse.class);
    }

    // ------------------------------------------------------------------
    // 评测
    // ------------------------------------------------------------------

    public EvalBatchResponse evaluationBatch(EvalBatchRequest request) {
        Map<String, Object> body = doRequest("/api/evaluation/batch", HttpMethod.POST, request, null);
        return parse(body, EvalBatchResponse.class);
    }

    // ------------------------------------------------------------------

    public Map<String, Object> runtimeConfig() {
        Map<String, Object> body = doRequest("/api/config", HttpMethod.GET, null, null);
        return body;
    }

    public boolean health() {
        try {
            restTemplate.getForEntity(url("/health"), String.class);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private <T> T parse(Map<String, Object> body, Class<T> clazz) {
        if (body == null) {
            throw new BusinessException(502, "AI 服务响应为空");
        }
        // FastAPI 成功时直接返回模型字段(非 Result 包装)
        return com.cyberrag.util.JsonUtil.convert(body, clazz);
    }
}
