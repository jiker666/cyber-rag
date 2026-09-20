package com.cyberrag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("message")
public class Message {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long conversationId;
    private String role;
    private String content;
    /** 引用来源 JSON 数组 */
    private String sources;
    /** 本次 RAG 决策轨迹 JSON(阶段耗时/路由/门控/缓存) */
    private String trace;
    private Integer retrievalTime;
    private Integer generationTime;
    private Integer totalTokens;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    @TableLogic
    private Integer deleted;
}
