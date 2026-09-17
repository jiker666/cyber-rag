package com.cyberrag.dto.rag;

import lombok.Data;

@Data
public class LlmOnlyRequest {
    private String question;
    private Double temperature;

    public LlmOnlyRequest() {
    }

    public LlmOnlyRequest(String question, Double temperature) {
        this.question = question;
        this.temperature = temperature;
    }
}
