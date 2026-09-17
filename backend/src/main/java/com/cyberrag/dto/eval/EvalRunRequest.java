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
}
