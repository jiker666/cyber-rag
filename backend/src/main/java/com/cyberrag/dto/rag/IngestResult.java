package com.cyberrag.dto.rag;

import lombok.Data;

@Data
public class IngestResult {
    private Integer chunkCount;
    private Integer charCount;
    private Long documentId;
    private Long knowledgeBaseId;
}
