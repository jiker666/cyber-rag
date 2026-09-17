"""FastAPI 应用入口。"""
import logging
import time

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import setup_logging

setup_logging(get_settings().log_level)
logger = logging.getLogger("cyber-rag.main")


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
