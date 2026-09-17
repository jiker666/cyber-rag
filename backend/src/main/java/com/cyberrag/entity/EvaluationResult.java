package com.cyberrag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("evaluation_result")
public class EvaluationResult {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long taskId;
    private Long itemId;
    private String question;
    private String mode;
    private String answer;
    private String sources;
    private Integer retrievalTime;
    private Integer generationTime;
    private Integer totalTime;
    private Integer promptTokens;
    private Integer completionTokens;
    /** 单题执行失败原因(成功为 NULL) */
    private String error;
    private Integer retrievalHit;
    private BigDecimal precisionAtK;
    private BigDecimal recallAtK;
    private BigDecimal keywordHitRate;
    private Integer citationMatched;
    private Integer manualCorrectness;
    private Integer manualRelevance;
    private Integer manualCompleteness;
    private Integer manualHallucination;
    private Integer manualScored;
    private String manualComment;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    @TableLogic
    private Integer deleted;
}
