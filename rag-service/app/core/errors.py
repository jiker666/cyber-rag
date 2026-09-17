"""统一异常定义与处理器。"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("cyber-rag.error")


class RagServiceError(Exception):
    """RAG 服务业务异常基类。"""

    def __init__(self, code: int = 500, message: str = "RAG 服务内部错误"):
        self.code = code
        self.message = message
        super().__init__(message)


class DocumentParseError(RagServiceError):
    def __init__(self, message: str = "文档解析失败"):
        super().__init__(code=422, message=message)


class EmbeddingError(RagServiceError):
    def __init__(self, message: str = "向量化失败"):
        super().__init__(code=502, message=message)


class LLMError(RagServiceError):
    def __init__(self, message: str = "大模型调用失败"):
        super().__init__(code=502, message=message)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RagServiceError)
    async def _rag_error(_: Request, exc: RagServiceError):
        return JSONResponse(
            status_code=exc.code, content={"code": exc.code, "message": exc.message, "data": None}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": str(exc.detail), "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": 422, "message": f"参数校验失败: {exc.errors()[:3]}", "data": None},
        )

    @app.exception_handler(Exception)
    async def _unknown_error(_: Request, exc: Exception):
        logger.exception("未处理异常: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "服务器内部错误", "data": None},
        )
