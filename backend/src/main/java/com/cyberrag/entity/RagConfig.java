package com.cyberrag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("rag_config")
public class RagConfig {
    @TableId(type = IdType.INPUT)
    private Long id;
    private Integer chunkSize;
    private Integer chunkOverlap;
    private Integer topK;
    private BigDecimal temperature;
    private BigDecimal scoreThreshold;
    private Integer enableReranker;
    private Integer rerankTopN;
    private Integer historyWindow;
    private Long updatedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
