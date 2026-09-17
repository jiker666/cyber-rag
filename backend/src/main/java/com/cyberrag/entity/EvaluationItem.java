package com.cyberrag.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("evaluation_item")
public class EvaluationItem {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long datasetId;
    private String question;
    private String referenceAnswer;
    private String expectedKeywords;
    private String expectedSource;
    private String category;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    @TableLogic
    private Integer deleted;
}
