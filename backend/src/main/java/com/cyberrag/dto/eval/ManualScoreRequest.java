package com.cyberrag.dto.eval;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 人工评分请求: 正确性/相关性/完整性 1-5, 幻觉判定。
 */
@Data
public class ManualScoreRequest {
    @NotNull @Min(1) @Max(5)
    private Integer correctness;

    @NotNull @Min(1) @Max(5)
    private Integer relevance;

    @NotNull @Min(1) @Max(5)
    private Integer completeness;

    /** 是否存在幻觉 */
    @NotNull
    private Boolean hallucination;

    private String comment;
}
