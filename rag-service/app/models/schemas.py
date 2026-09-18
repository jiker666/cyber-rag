"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel, ConfigDict, Field


# ---------------- 通用 ----------------
class IngestTextRequest(BaseModel):
    knowledge_base_id: int = Field(gt=0)
    document_id: int = Field(gt=0)
    document_name: str = Field(max_length=255)
    source: str = ""
    text: str = Field(min_length=1)
    chunk_size: int | None = Field(default=None, gt=0)
    chunk_overlap: int | None = Field(default=None, ge=0)


class IngestResult(BaseModel):
    """入库结果(对外序列化为 camelCase, 与 Java/前端契约一致)。"""

    model_config = ConfigDict(populate_by_name=True)

    chunk_count: int = Field(alias="chunkCount")
    char_count: int = Field(alias="charCount")
    document_id: int = Field(alias="documentId")
    knowledge_base_id: int = Field(alias="knowledgeBaseId")


# ---------------- 问答 ----------------
class ChatHistoryMsg(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    """问答请求: 同时接受 snake_case 与 Java 侧 camelCase 字段名。"""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=1, max_length=2000)
    knowledge_base_ids: list[int] = Field(default_factory=list, alias="knowledgeBaseIds")
    top_k: int | None = Field(default=None, ge=1, le=50, alias="topK")
    temperature: float | None = Field(default=None, ge=0, le=2)
    score_threshold: float | None = Field(default=None, ge=0, le=1, alias="scoreThreshold")
    enable_reranker: bool | None = Field(default=None, alias="enableReranker")
    rerank_top_n: int | None = Field(default=None, ge=1, le=50, alias="rerankTopN")
    retrieval_strategy: str | None = Field(default=None, pattern="^(vector|hybrid)$", alias="retrievalStrategy")
    history_window: int | None = Field(default=None, ge=0, le=20, alias="historyWindow")
    history: list[ChatHistoryMsg] = Field(default_factory=list)


class LlmOnlyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    temperature: float | None = Field(default=None, ge=0, le=2)


class SourceItem(BaseModel):
    documentId: int = 0
    documentName: str = ""
    knowledgeBaseId: int = 0
    chunkIndex: int = 0
    source: str = ""
    page: int | None = None
    content: str = ""
    score: float = 0.0
    rerankScore: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = []
    retrievalTime: int = 0
    generationTime: int = 0
    totalTime: int = 0
    promptTokens: int = 0
    completionTokens: int = 0
    totalTokens: int = 0
    retrievedCount: int = 0


# ---------------- 检索调试 ----------------
class RetrievalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=1, max_length=2000)
    knowledge_base_ids: list[int] = Field(min_length=1, alias="knowledgeBaseIds")
    top_k: int | None = Field(default=None, ge=1, le=50, alias="topK")
    score_threshold: float | None = Field(default=None, ge=0, le=1, alias="scoreThreshold")
    enable_reranker: bool | None = Field(default=None, alias="enableReranker")
    rerank_top_n: int | None = Field(default=None, ge=1, le=50, alias="rerankTopN")
    retrieval_strategy: str | None = Field(default=None, pattern="^(vector|hybrid)$", alias="retrievalStrategy")


# ---------------- 评测 ----------------
class EvalItem(BaseModel):
    """评测题目输入(同时接受 camelCase 别名, 对齐 Java 侧字段)。"""

    model_config = ConfigDict(populate_by_name=True)

    item_id: int = Field(gt=0, alias="itemId")
    question: str
    reference_answer: str | None = Field(default=None, alias="referenceAnswer")
    expected_keywords: str | None = Field(default=None, alias="expectedKeywords")
    expected_source: str | None = Field(default=None, alias="expectedSource")


class EvalParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    top_k: int | None = Field(default=None, ge=1, le=50, alias="topK")
    temperature: float | None = Field(default=None, ge=0, le=2)
    score_threshold: float | None = Field(default=None, ge=0, le=1, alias="scoreThreshold")
    enable_reranker: bool | None = Field(default=None, alias="enableReranker")
    rerank_top_n: int | None = Field(default=None, ge=1, le=50, alias="rerankTopN")
    retrieval_strategy: str | None = Field(default=None, pattern="^(vector|hybrid)$", alias="retrievalStrategy")


class EvalBatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: str = Field(pattern="^(LLM_ONLY|RAG_LLM)$")
    knowledge_base_id: int | None = Field(default=None, alias="knowledgeBaseId")
    params: EvalParams = Field(default_factory=EvalParams)
    items: list[EvalItem] = Field(min_length=1, max_length=100)


class EvalItemResult(BaseModel):
    """逐题评测结果(对外序列化 camelCase, 对齐 Java DTO)。"""

    model_config = ConfigDict(populate_by_name=True)

    item_id: int = Field(alias="itemId")
    question: str
    mode: str
    answer: str
    sources: list[SourceItem] = []
    retrieval_time: int = Field(default=0, alias="retrievalTime")
    generation_time: int = Field(default=0, alias="generationTime")
    total_time: int = Field(default=0, alias="totalTime")
    prompt_tokens: int = Field(default=0, alias="promptTokens")
    completion_tokens: int = Field(default=0, alias="completionTokens")
    retrieval_hit: bool | None = Field(default=None, alias="retrievalHit")
    precision_at_k: float | None = Field(default=None, alias="precisionAtK")
    recall_at_k: float | None = Field(default=None, alias="recallAtK")
    mrr: float | None = None
    keyword_hit_rate: float | None = Field(default=None, alias="keywordHitRate")
    citation_matched: float | None = Field(default=None, alias="citationMatched")
    error: str | None = None


class EvalMetrics(BaseModel):
    """任务级汇总指标(对外序列化 camelCase)。"""

    model_config = ConfigDict(populate_by_name=True)

    total: int = 0
    completed: int = 0
    failed: int = 0
    retrieval_hit_rate: float | None = Field(default=None, alias="retrievalHitRate")
    precision_at_k: float | None = Field(default=None, alias="precisionAtK")
    recall_at_k: float | None = Field(default=None, alias="recallAtK")
    mrr: float | None = None
    answer_keyword_accuracy: float | None = Field(default=None, alias="answerKeywordAccuracy")
    citation_validity: float | None = Field(default=None, alias="citationValidity")
    avg_retrieval_time_ms: float | None = Field(default=None, alias="avgRetrievalTimeMs")
    avg_generation_time_ms: float | None = Field(default=None, alias="avgGenerationTimeMs")
    avg_total_time_ms: float | None = Field(default=None, alias="avgTotalTimeMs")
    avg_total_tokens: float | None = Field(default=None, alias="avgTotalTokens")


class EvalBatchResponse(BaseModel):
    results: list[EvalItemResult]
    metrics: EvalMetrics


class ManualScore(BaseModel):
    """人工评分(持久化在 Java 侧, 此处仅作展示模型)。"""

    correctness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    hallucination: bool
    comment: str = ""
