"""FastAPI 应用入口。"""
import logging
import threading
import time

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import setup_logging

setup_logging(get_settings().log_level)
logger = logging.getLogger("cyber-rag.main")


def _warmup() -> None:
    """后台预热: Embedding 模型加载 + CrossEncoder 首次推理 + BM25 索引预建。

    避免首个用户请求承担模型冷启动(首问可达数秒)。预热失败不阻塞启动,
    仅记录日志 —— 服务仍可正常对外, 首问稍慢而已。
    """
    settings = get_settings()
    start = time.perf_counter()
    try:
        # 1. Embedding 模型加载 + 一次 encode(触发 tokenizer/权重加载)
        from app.embedding.factory import get_embedding_provider

        get_embedding_provider().embed_query("预热")
        logger.info("预热完成: embedding 模型已就绪 (%dms)", int((time.perf_counter() - start) * 1000))

        # 2. CrossEncoder 加载 + 一次 predict(首次推理含图优化/内存分配)
        if settings.reranker_enabled:
            from app.rag.reranker import get_reranker

            t2 = time.perf_counter()
            reranker = get_reranker(enabled=True)
            reranker.rerank("预热查询", ["预热文档片段"], top_n=1)
            logger.info(
                "预热完成: reranker 已就绪 (%dms)", int((time.perf_counter() - t2) * 1000)
            )
    except Exception as e:
        logger.warning("模型预热失败(不影响启动, 首问将承担冷启动): %s", e)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Cyber RAG Service",
        description="基于 RAG 的网络安全知识智能问答系统 - AI 服务端",
        version="1.0.0",
        docs_url="/docs",
    )
    install_exception_handlers(app)
    app.include_router(router)

    @app.get("/health", tags=["系统"])
    async def health():
        return {"status": "UP", "app": settings.app_name, "timestamp": int(time.time())}

    @app.on_event("startup")
    async def startup():
        logger.info(
            "RAG 服务启动: embedding=%s(%s), llm_model=%s, chroma=%s",
            settings.embedding_provider,
            settings.embedding_model,
            settings.llm_model,
            settings.chroma_persist_dir,
        )
        if settings.warmup_enabled:
            threading.Thread(target=_warmup, name="model-warmup", daemon=True).start()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=get_settings().rag_service_port,
        reload=False,
    )
