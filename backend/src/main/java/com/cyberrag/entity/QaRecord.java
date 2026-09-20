package com.cyberrag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("qa_record")
public class QaRecord {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long userId;
    private Long conversationId;
    private Long knowledgeBaseId;
    private String question;
    private String answer;
    private String sources;
    /** 本次 RAG 决策轨迹 JSON(阶段耗时/路由/门控/缓存) */
    private String trace;
    private Integer retrievalTime;
    private Integer generationTime;
    private Integer totalTime;
    private Integer totalTokens;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    @TableLogic
    private Integer deleted;
}
