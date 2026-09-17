package com.cyberrag.dto.kb;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class KbUpsertRequest {
    @NotBlank(message = "知识库名称不能为空")
    @Size(max = 100, message = "名称最长 100 字符")
    private String name;

    @Size(max = 500, message = "简介最长 500 字符")
    private String description;

    @Size(max = 50)
    private String category;

    private String coverColor;

    @Min(value = 0, message = "状态值非法")
    @Max(value = 1, message = "状态值非法")
    private Integer status = 1;
}
