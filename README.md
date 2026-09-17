# 基于 RAG 的网络安全知识智能问答系统

Retrieval-Augmented Generation based Cybersecurity Knowledge QA System

以"先检索、后生成、带引用"的方式, 将大语言模型锚定在受控的网络安全知识库之上, 实现**答案有依据、来源可追溯、幻觉可度量**的领域问答系统, 并内建 LLM_ONLY vs RAG 对照实验平台。

```
┌──────────────┐   /api (JWT)   ┌───────────────┐  X-Internal-Token  ┌──────────────────┐
│  Vue3 前端    │ ─────────────▶ │ Spring Boot   │ ─────────────────▶ │ FastAPI RAG 服务  │
│  Element Plus │                │ MyBatis-Plus  │                    │ BGE + Chroma     │
│  ECharts      │                │ MySQL (13 表) │                    │ LLM(OpenAI 兼容) │
└──────────────┘                └───────────────┘                    └──────────────────┘
```

## 功能特性

- **用户系统**: 注册登录(BCrypt 密码 + JWT 认证), 管理员/普通用户双角色
- **知识库管理**: 按安全子域分库, Chroma 集合级隔离, 统计概览
- **文档管理**: PDF/TXT/MD/DOCX 上传; 解析→清洗→分块→向量化异步流水线;
  状态机 `PENDING→PARSING→EMBEDDING→COMPLETED/FAILED`(失败可见原因, 可重试)
- **RAG 问答**: 多轮会话; 查询预处理→检索(向量 / 混合 BM25+RRF)→(可选)CrossEncoder 重排→上下文构造→LLM 生成;
  回答以 `[1][2]` 标注引用, 来源可展开(文档名/页码/相似度/原文); 支持重新生成、临时调参;
  Markdown 渲染 + 代码高亮 + 一键复制(默认转义防 XSS)
- **数据看板**: 用户/知识库/文档/问答统计卡片 + 近 7 天问答趋势 + 分类占比 + 知识库调用排行
- **参数配置**: ChunkSize/Overlap/Top-K/Temperature/阈值/检索策略/重排序/历史窗口, 全局可调
- **评估实验**: LLM_ONLY vs RAG_LLM 对照; Top-K {1,3,5,10}、ChunkSize {256,512,1024}、
  检索策略(vector/hybrid)、Reranker 开关扫描;
  自动指标(Hit Rate、P@K、R@K、MRR、关键词命中、引用准确率、耗时)+ 人工评分(1-5 分/幻觉标注);
  任务对比 + CSV 导出; 标准评测集见 `dataset/evaluation/`
- **安全实践**: 上传白名单/大小限制/随机文件名/防目录穿越; SQL 全参数化; 接口鉴权 + 管理员注解;
  API Key 仅环境变量; 日志脱敏; 前端零密钥

## 目录结构

```
cyber-rag/
├── frontend/        # Vue3 + TS + Element Plus + Pinia + ECharts
├── backend/         # Spring Boot 3(Java 21) + MyBatis-Plus + MySQL
├── rag-service/     # FastAPI + LangChain分块 + BGE + Chroma + LLM
├── sql/init.sql     # 13 张表 + 演示账号 + 15 道评测题
├── dataset/         # 30+ 篇网络安全示例知识文档(防御性学习内容)
├── docs/thesis/     # 论文支撑文档 8 篇
├── scripts/         # init.sh / run-local.sh
├── docker-compose.yml
└── .env.example
```

## 快速开始(Docker)

```bash
# 1. 配置环境变量(必填 LLM 三项; 密钥只存在于 .env, 严禁提交仓库)
cp .env.example .env
vim .env   # LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

# 2. 一键启动(mysql 自动执行 init.sql 初始化)
docker compose up -d --build

# 3. 访问
open http://localhost          # 前端
# 后端 http://localhost:8080/api | RAG 服务 http://localhost:8000/health
```

> 默认 Embedding 为本地 BGE 模型(首次启动需下载模型); 也可在 .env 中切换为 OpenAI 兼容 Embedding API。

## 快速开始(本机开发)

```bash
# 前置: JDK 21、Node 20+、Python 3.11+、MySQL 8
./scripts/init.sh        # 生成 .env 并初始化 MySQL(含演示数据)
./scripts/run-local.sh   # 同时启动 rag-service:8000 / backend:8080 / frontend:5173
```

或分服务启动:

```bash
# RAG 服务
cd rag-service && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000

# 后端(JDK 21)
cd backend && mvn spring-boot:run

# 前端
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## 演示账号

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员(知识库/文档/用户/参数/评估/看板) |
| user  | user123  | 普通用户(问答/会话/反馈) |

## 环境变量说明(节选, 完整见 .env.example)

| 变量 | 说明 | 默认 |
|------|------|------|
| `LLM_PROVIDER` | `openai`(兼容 /chat/completions) / `anthropic`(兼容 /v1/messages) | openai |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | LLM 配置(必填, 支持任意兼容接口) | - |
| `EMBEDDING_PROVIDER` | `local`(BGE 本地) / `openai`(兼容 API) | local |
| `EMBEDDING_MODEL` | 本地模型名 | BAAI/bge-m3(轻量可切 bge-small-zh-v1.5) |
| `JWT_SECRET` | JWT 密钥(≥32 字符, 生产必换) | - |
| `RAG_INTERNAL_TOKEN` | Java↔Python 内部令牌(两端一致) | - |
| `CHROMA_PERSIST_DIR` | 向量库目录 | ./data/chroma |
| `MAX_FILE_SIZE_MB` | 上传大小上限 | 20 |

密钥安全约定: API Key **只能**通过环境变量注入; 日志自动脱敏; 前端不保存任何密钥。

## RAG 原理简述

```
离线: 文档 → 解析(页级) → 清洗 → 中文语义分块(512/100) → BGE 向量化 → Chroma(kb_{id} 集合)
在线: 问题 → 预处理 → 向量化 → 检索(向量 Top-K / hybrid=向量+BM25 RRF 融合, 阈值过滤)
      → (可选 CrossEncoder 重排) → 编号上下文 [1][2]...
      → 系统提示(仅依据片段+必须引用+无依据拒答) → LLM
      → 回答 + 引用来源(文档/页码/相似度/原文/关键词命中标记)
```

## 运行测试

```bash
cd backend && mvn test                       # 34 项(H2 + Mockito)
cd rag-service && .venv/bin/python -m pytest # 67 项(离线 Fake 栈, 无需模型/网络)
cd frontend && npm run build                 # vue-tsc 类型检查 + 构建
```

## 本科毕设实验说明(全部为真实运行数据)

统一设置: LLM = glm-5.3-flash, Embedding = bge-small-zh-v1.5, 数据集 = 15 题(见 `dataset/evaluation/`),
知识库 = 20 篇安全文档(512/100 分块, 73 chunks), temperature = 0.3, 相似度阈值 = 0.3。
逐题原始数据: `docs/experiments/eval_task_*.csv`; 论文分析: `docs/thesis/06-实验设计.md`。

| 实验 | 任务 | 配置 | Hit@K | P@K | MRR | 关键词 | 引用 |
|---|---|---|---|---|---|---|---|
| E1 模式对照 | 4 | RAG K=5 | 1.0 | 0.32 | 0.867 | 0.840 | 1.0 |
| | 5 | LLM 直答 | — | — | — | 0.659 | — |
| E2 Top-K | 6/7/8 | K=1/3/10 | 0.73/1.0/1.0 | 0.73/0.45/0.25 | 0.73/0.80/0.87 | 0.81/0.82/**0.94** | 1.0/1.0/0.99 |
| E3 分块 | 9/10 | 256/1024 | 1.0/1.0 | 0.44/0.33 | 0.91/**0.93** | 0.78/**0.93** | 1.0/1.0 |
| D 混合检索 | 11 | 向量+BM25 RRF | 1.0 | **0.40** | 0.90 | 0.913 | 1.0 |
| E4 重排 | 14 | +CrossEncoder | 1.0 | **0.40** | **0.89** | **0.927** | 1.0 |

要点: RAG 较 LLM 直答关键词命中 +18.1pp 且引用可溯源; BM25+RRF 与 CrossEncoder 重排
均使 P@5 +8.0pp; E4 关键词命中率达全部实验最高。MRR 为程序化指标(Hit@K/P@K/MRR 由
`expectedSources` 与真实检索排序计算), 历史任务 MRR 经 `scripts/recompute-mrr.py` 补算并自校验。
复现: `scripts/run-experiment.sh [d|e4]`(需三服务已启动)。

## 验收流程(完整业务闭环)

1. admin 登录 → 新建知识库 → 上传 `dataset/` 文档(观察状态流转至 COMPLETED)
2. user 登录 → 选择知识库提问"如何防御 SQL 注入?" → 查看带 `[1]` 引用的回答并展开来源
3. admin → 数据看板查看统计 → 参数设置调 Top-K
4. 评估实验: 分别运行 LLM_ONLY 与 RAG_LLM → 查看逐题指标 → 人工评分 → 对比 → 导出 CSV

## 常见问题(FAQ)

**Q: 问答报错 "LLM 未配置"?**
`.env` 中 `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` 未填写或值非法, 配置后重启 rag-service。

**Q: 文档上传后一直 PENDING/FAILED?**
查看文档列表的失败原因; 常见: rag-service 未启动、内部令牌不一致、文件超过大小限制、PDF 为扫描件无可提取文本。

**Q: 首次启动很慢?**
本地 BGE 模型首次需下载(约 2GB); 显存/内存不足可切 `BAAI/bge-small-zh-v1.5` 或 OpenAI 兼容 Embedding API。国内网络可设置 `HF_ENDPOINT=https://hf-mirror.com` 加速。

**Q: 如何更换 LLM 厂商?**
任何兼容接口(GLM/Qwen/DeepSeek/OpenAI 等)只需改 `.env` 中的 LLM 变量, 无需改代码。智谱 BigModel 的 Anthropic 兼容通道示例:
`LLM_PROVIDER=anthropic`、`LLM_BASE_URL=https://open.bigmodel.cn/api/anthropic`、`LLM_MODEL=glm-5.3-flash`。

**Q: MySQL 初始化失败/重复初始化?**
`init.sql` 含 `DROP TABLE IF EXISTS`, 会清空重建业务表(不含向量库); 向量库目录可按需删除后重新上传文档。

## 声明

本系统知识内容限定于**防御性安全学习**(漏洞原理、防御方案、安全编码、法律法规), 不包含针对真实目标的攻击数据或工具。使用 LLM 服务需遵守对应服务商条款。
