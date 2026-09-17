package com.cyberrag.dto.chat;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class AskRequest {
    @NotBlank(message = "问题不能为空")
    @Size(min = 1, max = 2000, message = "问题长度 1-2000 字符")
    private String question;

    /** 会话 ID, 为空则新建会话 */
    private Long conversationId;

    /** 检索的知识库 ID */
    @NotNull(message = "请选择知识库")
    private Long knowledgeBaseId;

    @Min(1) @Max(50)
    private Integer topK;

    private Double temperature;

    private Boolean enableReranker;
}
