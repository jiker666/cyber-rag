# ---- rag-service Dockerfile ----
# 构建阶段无需额外编译, 直接使用精简 Python 镜像
FROM python:3.11-slim

WORKDIR /app

# 系统依赖(gb18030 编码支持等已内置于 Python)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 先装依赖(利用层缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 非 root 运行
RUN groupadd -r rag && useradd -r -g rag rag \
    && mkdir -p /app/data/chroma /app/data/uploads \
    && chown -R rag:rag /app
USER rag

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
