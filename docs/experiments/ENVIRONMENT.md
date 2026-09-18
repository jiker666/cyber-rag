# 实验环境与已测试版本(Tested Versions)

> 论文实验(E1-E3 / D / E4)的真实运行环境快照, 日期 2026-09-16 ~ 2026-09-17。
> 复现实验建议按下表对齐版本; Python 依赖完整快照见 `rag-service/requirements.lock.txt`
> (`pip freeze` 原样导出, `requirements.txt` 仍为开发用下界约束)。

## 1. 硬件与操作系统

| 项 | 值 |
|---|---|
| 机器 | MacBook Pro (Apple Silicon, arm64) |
| CPU | Apple M3 Pro |
| 内存 | 18 GB |
| 操作系统 | macOS 14 (Darwin 23.6.0) |
| 加速 | Embedding/Reranker 以 CPU 推理(未使用 GPU) |

## 2. 运行时与中间件

| 组件 | 实验环境版本 | 仓库内对应 |
|---|---|---|
| Python | 3.13.13(本机 venv) | Docker 镜像 `python:3.11-slim` |
| JDK | OpenJDK 21.0.11(注: JDK 25 下 Lombok 注解处理失效, 须用 21) | `backend/Dockerfile` temurin-21 |
| Node.js | v22.22.3 | Docker 镜像 `node:20-alpine` |
| MySQL | 8.4.9(本机) | Docker 镜像 `mysql:8.4` |
| 前端构建 | vite + vue-tsc(`npm run build` 通过) | `frontend/package.json` |

## 3. 关键 Python 依赖(本机实验环境实测版本)

| 包 | 版本 | 用途 |
|---|---|---|
| fastapi | 0.141.1 | RAG 服务框架 |
| uvicorn | 0.53.0 | ASGI Server |
| pydantic / pydantic-settings | 2.13.5 / 2.15.0 | 模型与配置 |
| chromadb | 1.5.9 | 向量库 |
| sentence-transformers | 6.0.1 | Embedding / CrossEncoder |
| torch | 2.14.0 | 推理后端(CPU) |
| langchain-text-splitters | 1.1.2 | 中文语义分块 |
| openai | 3.14.1 | OpenAI 兼容客户端 |
| pypdf / python-docx | 6.19.0 / 1.2.0 | PDF / DOCX 解析 |
| httpx | 0.28.1 | Anthropic 兼容通道 HTTP 客户端 |
| pytest | 9.1.1 | 测试 |

完整传递依赖闭包见 `rag-service/requirements.lock.txt`(123 项, `pip freeze` 导出)。

## 4. 模型与 LLM(实验配置)

| 角色 | 模型 | 说明 |
|---|---|---|
| LLM | glm-5.3-flash | 智谱 BigModel, Anthropic 兼容通道(`/api/anthropic`); temperature=0.3 |
| Embedding | BAAI/bge-small-zh-v1.5 | 本地推理, 输出 512 维, 归一化后余弦相似度 |
| Reranker(E4) | BAAI/bge-reranker-base | CrossEncoder, max_length=512, 进程级单例 |
| 向量库 | Chroma(持久化, cosine) | 每知识库独立 Collection `kb_{id}` |

密钥均经环境变量注入, 不落盘不入库; 本文件不含任何密钥。

## 5. 数据与统一实验参数

- 评测集: `dataset/evaluation/cyber_security_qa_15.json`(15 题, 单期望来源标注);
- 知识库: 20 篇安全文档, 512/100 分块共 73 chunks(E3 另建 256/50 与 1024/200 索引);
- 参数: top_k=5(除 E2 扫描), score_threshold=0.3, temperature=0.3, RRF k=60;
- 原始数据: `docs/experiments/eval_task_*.csv`(UTF-8 BOM, 由系统导出接口生成)。

## 6. 复现方式

1. 按 `README.md` 启动三服务(本机或 Docker 均可; 建议先 `pip install -r rag-service/requirements.lock.txt`);
2. 首次启动会自动下载本地模型(Embedding 约 100MB ~ 2GB, 视所选模型; Reranker 约 1.1GB);
3. 建知识库并上传 `dataset/` 文档, 等待状态 COMPLETED;
4. `scripts/run-experiment.sh [d|e4]` 复现混合检索/重排对照(E1-E3 经评估页手工发起);
5. 耗时类指标受网络与硬件影响, 与论文数值允许存在差异; 质量类指标(命中率/P@K/MRR/关键词)在同数据同参数下应可复现(LLM 采样仍引入随机性, temperature=0.3 仅降低而非消除)。
