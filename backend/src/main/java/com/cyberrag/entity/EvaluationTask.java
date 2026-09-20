package com.cyberrag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("evaluation_task")
public class EvaluationTask {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;
    private String mode;
    private Long knowledgeBaseId;
    private Long datasetId;
    private Integer topK;
    private Integer chunkSize;
    private Integer chunkOverlap;
    private BigDecimal temperature;
    private Integer enableReranker;
    private String retrievalStrategy;
    /** Adaptive RAG 总开关(NULL 未指定, 跟随 rag-service 全局配置) */
    private Integer adaptiveEnabled;
    private Integer entityBoost;
    private Integer rerankGating;
    private Integer dynamicContext;
    private Integer useCaches;
    private Integer total;
    private Integer completed;
    private Integer failed;
    private String status;
    /** 汇总指标 JSON */
    private String metrics;
    private String errorMsg;
    private Long createdBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    @TableLogic
    private Integer deleted;
}
