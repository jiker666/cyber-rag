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
    private BigDecimal ndcgAtK;
    private BigDecimal mrr;
    private BigDecimal keywordHitRate;
    private Integer citationMatched;
    /** Performance Detail: 自适应路由(非自适应为 NULL) */
    private String route;
    /** Performance Detail: 是否触发重排(非自适应为 NULL) */
    private Integer rerankUsed;
    /** Performance Detail: 上下文 token 数(启发式估算) */
    private Integer contextTokens;
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
