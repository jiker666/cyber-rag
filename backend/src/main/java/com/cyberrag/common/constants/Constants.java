package com.cyberrag.common.constants;

/**
 * 系统常量。
 */
public final class Constants {

    private Constants() {
    }

    /** 角色编码 */
    public static final String ROLE_ADMIN = "ADMIN";
    public static final String ROLE_USER = "USER";
    public static final long ROLE_ID_ADMIN = 1L;
    public static final long ROLE_ID_USER = 2L;

    /** 文档状态 */
    public static final String DOC_PENDING = "PENDING";
    public static final String DOC_PARSING = "PARSING";
    public static final String DOC_EMBEDDING = "EMBEDDING";
    public static final String DOC_COMPLETED = "COMPLETED";
    public static final String DOC_FAILED = "FAILED";

    /** 允许上传的扩展名 */
    public static final java.util.Set<String> ALLOWED_EXTENSIONS =
            java.util.Set.of("pdf", "txt", "md", "markdown", "docx");

    /** 评测任务状态 */
    public static final String TASK_PENDING = "PENDING";
    public static final String TASK_RUNNING = "RUNNING";
    public static final String TASK_COMPLETED = "COMPLETED";
    public static final String TASK_FAILED = "FAILED";

    /** 评测模式 */
    public static final String MODE_LLM_ONLY = "LLM_ONLY";
    public static final String MODE_RAG_LLM = "RAG_LLM";

    /** 消息角色 */
    public static final String MSG_USER = "user";
    public static final String MSG_ASSISTANT = "assistant";
}
