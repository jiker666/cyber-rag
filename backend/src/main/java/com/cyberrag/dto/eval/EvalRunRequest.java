package com.cyberrag.dto.eval;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 发起评测任务请求。
 */
@Data
public class EvalRunRequest {
    @NotBlank(message = "任务名称不能为空")
    @Size(max = 100)
    private String name;

    /** LLM_ONLY / RAG_LLM */
    @NotBlank(message = "模式不能为空")
    private String mode;

    /** RAG 模式下检索的知识库 */
    private Long knowledgeBaseId;

    @NotNull(message = "请选择评测数据集")
    private Long datasetId;

    @Min(1) @Max(50)
    private Integer topK;

    @Min(64) @Max(4096)
    private Integer chunkSize;

    @Min(0) @Max(4096)
    private Integer chunkOverlap;

    private Double temperature;

    private Boolean enableReranker;

    /** vector / hybrid */
    private String retrievalStrategy;

    // ---- Adaptive RAG(对比实验 E5-D / 消融实验开关) ----
    /** 自适应总开关(查询分析+路由+门控+动态上下文) */
    private Boolean adaptive;
    /** 实体精确加权(消融: -Entity Boost) */
    private Boolean entityBoost;
    /** 置信度门控重排(消融: -Reranker Gating, 关闭后回退 enableReranker 固定开关) */
    private Boolean rerankGating;
    /** 动态上下文预算(消融: -Dynamic Context) */
    private Boolean dynamicContext;
    /** Embedding/检索缓存(消融: -Cache; E5 对比实验统一关闭) */
    private Boolean useCaches;
}
