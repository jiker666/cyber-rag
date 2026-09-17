# Cyber-RAG 第二轮项目审计报告（PROJECT_AUDIT）

> 审计日期: 2026-09-17
> 审计方式: 全量代码阅读（backend 34 文件 / rag-service 40+ 文件 / frontend 20+ 文件）+ 三端真实构建与测试运行。
> 结论先行: **项目为真实 RAG 系统, 无伪实现**。P0/P1 基本就绪, 缺口集中在前端 Markdown 渲染、E4/D 实验未执行、部分文档未补。

---

## 一、构建与测试基线（本轮实测）

| 端 | 命令 | 结果 |
|---|---|---|
| Python RAG 服务 | `pytest` | ✅ 58/58 通过（16.6s） |
| Spring Boot | `mvn test` | ✅ 34/34 通过，BUILD SUCCESS |
| 前端 | `npm run build` | ✅ vue-tsc + vite 通过 |

代码卫生: 全仓库无 TODO/FIXME/debug 残留; 无硬编码 URL/密码/Key; `.env` 已 gitignore 且未入库。

---

## 二、模块完成度清单

### 基础系统
| 项 | 状态 | 依据 |
|---|---|---|
| 注册 | ✅ | `UserServiceTest`(4 用例), RegisterView, BCrypt |
| 登录 | ✅ | `AuthApiTest`(5 用例), JWT 签发 |
| JWT | ✅ | `JwtUtil` + `AuthInterceptor`, Secret 从环境变量读 |
| 用户管理 | ✅ | UserManageView + `@RequireAdmin` |
| 角色权限 | ✅ | ADMIN/USER, `RequireAdmin` 注解拦截 |
| 个人信息 | ✅ | ProfileView + FeedbackController |

### 知识库
| 项 | 状态 | 依据 |
|---|---|---|
| 创建/编辑/删除/列表/详情 | ✅ | KnowledgeBaseServiceImpl; 删除前置校验"库内文档须清空", 删除时同步清理 Chroma Collection |

### 文档摄取
| 项 | 状态 | 依据 |
|---|---|---|
| PDF/MD/TXT/DOCX 解析 | ✅ | `document/parser.py` |
| 文本清洗 | ✅ | `document/cleaner.py` |
| Chunk(512/100 可配) | ✅ | `rag/chunker.py`, `test_chunker.py` |
| Embedding | ✅ | BAAI/bge-small-zh-v1.5, 批量写入 |
| 向量存储 | ✅ | Chroma 持久化, 每知识库一个 Collection |
| 删除文档 | ✅ | 先删向量→再删业务记录→再删源文件(`delete_by_document` where document_id) |
| 重新处理 | ✅ | `POST /documents/{id}/reingest` |
| 处理状态机 | ✅ | PENDING→PARSING→EMBEDDING→COMPLETED/FAILED, 失败原因落库 |
| 上传安全 | ✅ | 扩展名白名单+UUID 落盘+防目录穿越(normalize+startsWith)+大小限制+管理员限定 |
| Chunk Metadata | ✅ | document_id/name, knowledge_base_id, chunk_index, source, page(PDF 页码) |

### RAG 核心
| 项 | 状态 | 依据 |
|---|---|---|
| Query Embedding | ✅ | `retriever.py` embed_query |
| Vector Retrieval + Top-K | ✅ | Chroma cosine, 多库归并排序 |
| Context Builder | ✅ | `context_builder.py` |
| LLM | ✅ | Anthropic 兼容协议(glm-5.3-flash), 可切换 provider |
| Citation 真实性 | ✅ | sources 严格来自检索命中的 chunk(`RetrievedChunk.to_dict`), 系统提示禁止编造引用 |
| 多知识库隔离 | ✅ | 每库独立 Collection(`kb_{id}`), `test_retriever.py` 隔离用例 |
| 阈值过滤 | ✅ | `score_threshold` 默认 0.3, `test_threshold_filters_results` |
| 无知识场景 | ✅(提示词策略) | 检索为空→context 置"(未检索到相关内容)"+ 系统提示规则 3: 明确声明无依据、通用知识须标注 |
| Reranker | ✅(实现/默认关) | CrossEncoder(bge-reranker-base) 懒加载, 参数链前端→Java→Python 全通; **模型未下载、实验未跑(本轮补)** |
| Hybrid BM25 | ❌ 未实现 | 本轮作为可开关策略补充并用真实评测验证(P3) |

### 对话
| 项 | 状态 | 依据 |
|---|---|---|
| 会话/历史/消息持久化/删除 | ✅ | conversation/message 表 + ChatController |
| 多轮(历史窗口) | ✅ | pipeline history_window 裁剪 |
| 重新生成 | ✅ | regenerate 端点 |
| 引用展开 | ✅ | SourceList 折叠面板: 文档名/页码/原文/相似度 |
| SSE 流式 | ❌ 未实现 | 记录为已知限制(实现成本涉及三端改造, 本轮不做) |

### Dashboard
| 项 | 状态 |
|---|---|
| 用户/知识库/文档/Chunk/问答统计, 7 日趋势, 库占比, 分类图 | ✅ 真实 SQL 聚合 |

### Evaluation
| 项 | 状态 | 依据 |
|---|---|---|
| LLM Only vs RAG | ✅ | `llm_only_chat` 对照组, E1 已跑: 关键词命中 84% vs 66% |
| 批量评测 + 指标 | ✅ | Hit@K / Precision@K / Recall@K / 关键词覆盖 / 引用准确率(程序计算, 非 LLM 伪造) |
| MRR | ❌ | 本轮补(数据允许: 有 expected_source) |
| Top-K 实验 | ✅ | E2 已跑(K=1/3/5/10) |
| Chunk Size 实验 | ✅ | E3 已跑(256/512/1024) |
| Reranker 实验 | ❌ | 本轮补(E4) |
| Hybrid 实验 | ❌ | 本轮补(D) |
| CSV 导出 | ✅ | `docs/experiments/eval_task_4..10.csv`(真实运行产物) |
| 人工评分 | ✅ | ManualScoreRequest(正确性/相关性/完整性) + FeedbackController |
| 评测数据集 | ✅(库内) | 10 任务 150 题; 标准格式 JSON 导出本轮补到 `dataset/evaluation/` |
| 评测页 reranker 开关 | ❌ | 前端 EvaluationView 未暴露 enableReranker, 本轮补 |

### 工程
| 项 | 状态 |
|---|---|
| Docker | ✅ docker-compose(mysql/backend/rag/frontend), 本轮校验依赖关系 |
| README | ✅ 已可跑通; 本轮补评测运行/实验说明/截图 |
| 集成测试(上传→处理→检索) | ✅ `test_api.py` 走真实 vector store, LLM mock 仅限 LLM 边界 |
| 日志脱敏 | ✅ SensitiveFilter(sk-*/Bearer/api_key 打码) |
| CORS | ✅ 开发宽松可配置 |

---

## 三、本轮发现的问题与缺口（按优先级）

| # | 优先级 | 问题 | 处理 |
|---|---|---|---|
| 1 | P2 | 前端聊天仅行内 code 正则替换, 无 Markdown 渲染/代码高亮/Copy | 本轮实现(markdown-it + highlight.js, 默认转义防 XSS) |
| 2 | P3 | bge-reranker-base 未下载, E4 实验未执行 | 后台下载中 → 跑真实实验 → CSV + 论文 |
| 3 | P3 | Hybrid(BM25+RRF) 未实现, 安全术语(CWE-918 等)精确召回无保障 | 实现为可开关策略 + Experiment D 评测 |
| 4 | P1 | 缺 MRR 指标 | 补 metrics + 聚合 + CSV 字段 |
| 5 | P1 | 评测集无标准 JSON 落盘 | 导出 `dataset/evaluation/` + example |
| 6 | P2 | EvaluationView 无 reranker/检索策略开关 | 补 UI |
| 7 | P2 | 论文文档缺: 检索策略设计、答辩演示流程、Mermaid 架构/时序/ER 图 | 补文档 |
| 8 | P3 | SSE 流式未实现 | 不做, 记录为已知限制 |

## 四、伪实现排查结论

逐项检查 prompt 列举的 13 类伪实现(假登录/假统计/假检索/固定回答/写死数据/Mock API/随机相似度/随机指标/假引用/LLM 冒充 RAG/上传不入库/删除残留/假按钮): **均未发现**。统计为真实 SQL 聚合, 相似度为 Chroma 真实余弦距离换算, 指标由程序基于检索结果计算, 实验数据 CSV 与运行日志可复现。
