"""API 路由: 文档入库 / 问答 / 检索 / 配置 / 评测。"""
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    EvalBatchRequest,
    EvalBatchResponse,
    IngestResult,
    IngestTextRequest,
    LlmOnlyRequest,
    RetrievalRequest,
)
from app.embedding.factory import get_embedding_provider
from app.evaluation.runner import EvaluationRunner
from app.llm.factory import get_llm_provider
from app.rag.pipeline import ChatHistoryItem, RagParams, RagPipeline
from app.rag.retriever import Retriever
from app.vectorstore.chroma_store import get_vector_store

logger = logging.getLogger("cyber-rag.api")


async def verify_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """内部令牌校验: Java 后端调用 RAG 服务需携带一致令牌。"""
    token = get_settings().rag_internal_token
    if token and x_internal_token != token:
        raise HTTPException(status_code=401, detail="内部令牌校验失败")


router = APIRouter(prefix="/api", dependencies=[Depends(verify_internal_token)])


# =====================================================================
# 文档入库
# =====================================================================
@router.post("/ingest/file", response_model=IngestResult)
async def ingest_file_endpoint(
    file: UploadFile = File(...),
    knowledge_base_id: int = Form(...),
    document_id: int = Form(...),
    filename: str | None = Form(default=None),
    chunk_size: int | None = Form(default=None),
    chunk_overlap: int | None = Form(default=None),
):
    """文件上传入库: 由 Java 后端在文档状态流转中调用。"""
    from app.api.ingest_service import ingest_file

    settings = get_settings()
    # 随机文件名 + 白名单扩展名, 防目录穿越与恶意文件
    # filename: Java 后端显式传递的原始文件名(优先); 否则回退 multipart 文件名
    original_name = os.path.basename(filename or file.filename or "unnamed")
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in {".pdf", ".txt", ".md", ".markdown", ".docx"}:
        raise HTTPException(status_code=422, detail=f"不支持的文件类型: {ext}")

    upload_dir = os.path.abspath(settings.upload_dir)
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(upload_dir, stored_name)
    try:
        size = 0
        with open(stored_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_file_size_mb * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"文件超过 {settings.max_file_size_mb}MB 限制")
                out.write(chunk)
        result = ingest_file(
            file_path=stored_path,
            filename=original_name,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return IngestResult(
            chunk_count=result["chunk_count"],
            char_count=result["char_count"],
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文件入库失败: %s", original_name)
        raise HTTPException(status_code=500, detail=f"入库失败: {e}")
    finally:
        # 入库后清理临时文件(向量库已持久化语义)
        try:
            os.remove(stored_path)
        except OSError:
            pass


@router.post("/ingest/text", response_model=IngestResult)
async def ingest_text_endpoint(req: IngestTextRequest):
    from app.api.ingest_service import ingest_text

    result = ingest_text(
        text=req.text,
        document_name=req.document_name,
        source=req.source or req.document_name,
        knowledge_base_id=req.knowledge_base_id,
        document_id=req.document_id,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
    )
    return IngestResult(
        chunk_count=result["chunk_count"],
        char_count=result["char_count"],
        document_id=req.document_id,
        knowledge_base_id=req.knowledge_base_id,
    )


@router.delete("/ingest/document/{knowledge_base_id}/{document_id}")
async def delete_document_vectors(knowledge_base_id: int, document_id: int):
    get_vector_store().delete_by_document(knowledge_base_id, document_id)
    return {"code": 0, "message": "ok", "data": None}


@router.delete("/ingest/collection/{knowledge_base_id}")
async def delete_collection(knowledge_base_id: int):
    get_vector_store().delete_collection(knowledge_base_id)
    return {"code": 0, "message": "ok", "data": None}


@router.get("/ingest/stats/{knowledge_base_id}")
async def ingest_stats(knowledge_base_id: int):
    store = get_vector_store()
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "chunkCount": store.count(knowledge_base_id),
            "documentCount": store.document_count(knowledge_base_id),
        },
    }


# =====================================================================
# 问答
# =====================================================================
@router.post("/chat/query", response_model=ChatResponse)
async def chat_query(req: ChatRequest):
    """RAG 增强问答。"""
    pipeline = RagPipeline()
    params = RagParams(
        top_k=req.top_k,
        temperature=req.temperature,
        score_threshold=req.score_threshold,
        enable_reranker=req.enable_reranker,
        rerank_top_n=req.rerank_top_n,
        retrieval_strategy=req.retrieval_strategy,
        history_window=req.history_window,
    )
    history = [ChatHistoryItem(role=h.role, content=h.content) for h in req.history]
    result = pipeline.rag_chat(req.question, req.knowledge_base_ids, params, history)
    return ChatResponse(**result.to_dict())


@router.post("/chat/llm-only", response_model=ChatResponse)
async def chat_llm_only(req: LlmOnlyRequest):
    """对照组: 仅 LLM 直接回答。"""
    pipeline = RagPipeline()
    result = pipeline.llm_only_chat(req.question, RagParams(temperature=req.temperature))
    return ChatResponse(**result.to_dict())


# =====================================================================
# 检索调试
# =====================================================================
@router.post("/retrieval/search")
async def retrieval_search(req: RetrievalRequest):
    retriever = Retriever()
    chunks = retriever.retrieve(
        query=req.question,
        knowledge_base_ids=[int(k) for k in req.knowledge_base_ids],
        top_k=req.top_k,
        score_threshold=req.score_threshold,
        enable_reranker=req.enable_reranker,
        rerank_top_n=req.rerank_top_n,
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {"question": req.question, "chunks": [c.to_dict() for c in chunks]},
    }


# =====================================================================
# 运行时信息(不含任何密钥)
# =====================================================================
@router.get("/config")
async def runtime_config():
    settings = get_settings()
    embedding_info: dict
    try:
        embedding_info = get_embedding_provider().info()
    except Exception:
        embedding_info = {"provider": settings.embedding_provider, "model": settings.embedding_model,
                          "dimension": settings.embedding_dimension}
    llm_info: dict
    try:
        llm = get_llm_provider()
        llm_info = {"provider": llm.name, "model": llm.model}
    except Exception:
        llm_info = {"provider": "openai-compatible", "model": settings.llm_model, "error": "LLM 未配置"}
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "embedding": embedding_info,
            "llm": llm_info,
            "reranker": {"enabled": settings.reranker_enabled, "model": settings.reranker_model},
            "vectorStore": {"type": "chroma", "persistDir": settings.chroma_persist_dir},
            "retrieval": {"strategy": settings.retrieval_strategy},
            "defaults": {
                "chunkSize": settings.default_chunk_size,
                "chunkOverlap": settings.default_chunk_overlap,
                "topK": settings.default_top_k,
                "temperature": settings.default_temperature,
                "scoreThreshold": settings.default_score_threshold,
            },
        },
    }


# =====================================================================
# 评测
# =====================================================================
@router.post("/evaluation/batch", response_model=EvalBatchResponse)
def evaluation_batch(req: EvalBatchRequest):
    """批量评测: 真实运行并返回逐题结果与汇总指标。

    注意保持同步 def: run_batch 为阻塞式长任务(逐题调用 LLM),
    同步函数会被 FastAPI 放入线程池执行, 避免卡死事件循环导致问答不可用。
    """
    runner = EvaluationRunner(pipeline=RagPipeline())
    results, agg = runner.run_batch(req)
    return EvalBatchResponse(
        results=results,
        metrics=agg,  # type: ignore[arg-type]
    )
